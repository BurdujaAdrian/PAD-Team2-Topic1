# PAD-Team2-Topic1
PAD Team 2's Common Public Repository

# Service Boundaries

## Player Service
Owns the player's identity, friends and online presence, inventory, player progression(XP), trading between players(Including ensuring correctness and making trades across lobbies).

Does not own the item recipes or their acquisition - Crafting service does; Player service only receives the items from the Crafting service after they are crafted.

Does not own the real-time actions state - Game Service does; Game service tells which stats to update with the corresponding values.

## Game Service
Owns the active sessions, the day-night cycle, session timers and timed events, the spawning and short-lived behavior of Zombies during a cycle.

Does not own players inventory or progress - Player Service does; Game service can ask for the players current state.

Does not own the state of the map - World Service does; Game Service requests changes (clear room, barricade room) and reads current state via query. It holds no local copy, so there's one source of truth.

Does not own the state of the base - Base Service does; Game Service triggers the repair/upgrade timed action, Base Service validates and applies the resulting persistent change.

Does not own resource quantities - Resource Service does; Game Service only runs the timer for a gathering action, Resource Service validates and applies the resulting resource change once it completes.

Does not own the exam system - Exam Service does; Game Service can request exams.

Does not own the configuration of zombies - Zombie Service does; Game Service can query the Zombie Service for configurations.

## Exam Service
Owns exam definitions, the static question bank, exam attempts, scores, pass/fail
results, per-course progress, grades, achievements and diploma milestones.

Does not own player identity, XP or levels - Player Service owns them; Exam Service
publishes `ExamCompleted` and `AchievementUnlocked`, and Player Service applies the
reward itself.

Does not own the player's inventory - Player Service owns it; rewards travel as event
payloads and are never written directly by Exam Service.

Does not own the campus map or wing unlocking - World Service owns it; Exam Service
publishes `ExamPassed` and World Service decides which section to generate.

Does not own encounters, the day/night cycle or action timers - Game Service owns them;
Game Service synchronously requests an exam when a player meets a Professor Zombie.

Does not own zombie definitions or behaviour - Zombie Service owns them; Exam Service
never contacts it, since Game Service mediates the whole encounter.

### Endpoints
 
#### Start an Exam Attempt
 
`POST /api/exams/attempts` Description: Starts an exam for a player who encountered a Professor Zombie. Called by the Game Service. Idempotent by `encounter_id`. Payload:
 
```json
{
  "player_id": "player-uuid-123",
  "game_session_id": "session-uuid-456",
  "encounter_id": "encounter-uuid-789",
  "course_id": "math_analysis"
}
```
 
Success Response (201 Created):
 
```json
{
  "attempt_id": "attempt-uuid-001",
  "player_id": "player-uuid-123",
  "course_id": "math_analysis",
  "status": "in_progress",
  "time_limit_seconds": 300,
  "pass_threshold": 0.6,
  "questions": [
    {
      "question_id": "question-uuid-011",
      "text": "What is the derivative of x^2?",
      "options": [
        { "option_id": "option-uuid-a", "text": "2x" },
        { "option_id": "option-uuid-b", "text": "x" }
      ]
    }
  ],
  "started_at": "2026-09-08T14:32:00Z"
}
```
 
Error Responses: `404 Not Found` — no exam available for this player. `409 Conflict` — player already has an attempt in progress.
 
#### Get Attempt State
 
`GET /api/exams/attempts/{attempt_id}` Description: Returns the current state of an attempt, without the correct answers.
 
Success Response (200 OK):
 
```json
{
  "attempt_id": "attempt-uuid-001",
  "player_id": "player-uuid-123",
  "course_id": "math_analysis",
  "status": "in_progress",
  "answered_count": 3,
  "total_questions": 5,
  "remaining_seconds": 142,
  "started_at": "2026-09-08T14:32:00Z"
}
```
 
#### Submit an Answer
 
`POST /api/exams/attempts/{attempt_id}/answers` Description: Records one answer. A repeated answer to the same question overwrites the previous one. Payload:
 
```json
{
  "question_id": "question-uuid-011",
  "option_id": "option-uuid-a"
}
```
 
Success Response (202 Accepted):
 
```json
{
  "question_id": "question-uuid-011",
  "recorded": true,
  "answered_count": 4,
  "total_questions": 5
}
```
 
Error Responses: `409 Conflict` — attempt already submitted or expired. `422 Unprocessable Entity` — question does not belong to this attempt.
 
#### Finish the Exam
 
`POST /api/exams/attempts/{attempt_id}/submit` Description: Finalises the attempt, computes the score and publishes the resulting events. Idempotent — a second call returns the stored result.
 
Success Response (200 OK):
 
```json
{
  "attempt_id": "attempt-uuid-001",
  "player_id": "player-uuid-123",
  "course_id": "math_analysis",
  "score": 0.8,
  "correct_answers": 4,
  "total_questions": 5,
  "passed": true,
  "attempts_remaining": 2,
  "achievements_unlocked": ["survived_the_pumpkin"],
  "submitted_at": "2026-09-08T14:36:12Z"
}
```
 
#### Get Academic Progress
 
`GET /api/players/{player_id}/progress` Description: Returns the player's academic progression. Consumed by the client and by the Crafting Service for exam-gated recipes.
 
Success Response (200 OK):
 
```json
{
  "player_id": "player-uuid-123",
  "passed_count": 3,
  "total_courses": 8,
  "courses": [
    {
      "course_id": "math_analysis",
      "name": "Mathematical Analysis",
      "status": "passed",
      "best_score": 0.8,
      "attempts_used": 1,
      "attempts_remaining": 2
    }
  ]
}
```
 
#### Get Achievements
 
`GET /api/players/{player_id}/achievements` Description: Returns the achievements unlocked by the player.
 
Success Response (200 OK):
 
```json
{
  "player_id": "player-uuid-123",
  "achievements": [
    {
      "achievement_id": "survived_the_pumpkin",
      "name": "Survived the Pumpkin",
      "unlocked_at": "2026-09-08T14:36:12Z"
    }
  ]
}
```
 

## World Service
Owns the persistent campus map, room types, resource node placement, zombie spawn
points and their configuration, section unlock state and procedural generation rules.

Does not own resource quantities or transactions - Resource Service owns them; World
Service publishes `SectionUnlocked` and Resource Service creates the economy entries
for the new nodes.

Does not own what players have built - Base Service owns it; Base Service references
room identifiers, while World Service stores no construction state at all.

Does not own zombie stats or behaviour - Zombie Service owns them; World Service stores
only zombie type references inside spawn points, which Game Service resolves.

Does not own game sessions, timers or action progress - Game Service owns them; Game
Service synchronously queries rooms, resource nodes and spawn points when needed.

Does not own the academic rules that trigger unlocking - Exam Service owns them; World
Service consumes `ExamPassed` and applies its own mapping, idempotent by attempt.

### Endpoints
 
#### Get the Campus Map
 
`GET /api/worlds/{world_id}/map` Description: Returns the full topology. Query parameter `unlocked` (boolean, defaults to `true`) filters locked sections.
 
Success Response (200 OK):
 
```json
{
  "world_id": "world-uuid-100",
  "version": 7,
  "rooms": [
    {
      "room_id": "room-uuid-201",
      "name": "FAF Cab",
      "type": "fafcab",
      "section_id": "section-uuid-301",
      "floor": 3,
      "unlocked": true,
      "adjacent_room_ids": ["room-uuid-202", "room-uuid-203"]
    }
  ]
}
```
 
#### List Rooms
 
`GET /api/worlds/{world_id}/rooms` Description: Returns rooms filtered by `type`, `unlocked` or `section_id`. Used by the Game Service to determine where actions are possible.
 
Success Response (200 OK):
 
```json
{
  "world_id": "world-uuid-100",
  "count": 12,
  "rooms": [
    {
      "room_id": "room-uuid-204",
      "name": "Library",
      "type": "library",
      "section_id": "section-uuid-301",
      "floor": 2,
      "unlocked": true,
      "adjacent_room_ids": ["room-uuid-205"]
    }
  ]
}
```
 
#### Get Resource Nodes in a Room
 
`GET /api/rooms/{room_id}/resource-nodes` Description: Returns node placement and regeneration configuration. Current quantities belong to the Resource Service.
 
Success Response (200 OK):
 
```json
{
  "room_id": "room-uuid-204",
  "nodes": [
    {
      "node_id": "node-uuid-401",
      "resource_type": "paper",
      "regen_rate_per_minute": 2,
      "max_capacity": 50
    }
  ]
}
```
 
Error Responses: `404 Not Found` — unknown or still locked room.
 
#### Get Spawn Points in a Room
 
`GET /api/rooms/{room_id}/spawn-points` Description: Returns the spawn configuration for a room. Zombie statistics and behaviour belong to the Zombie Service.
 
Success Response (200 OK):
 
```json
{
  "room_id": "room-uuid-204",
  "spawn_points": [
    {
      "spawn_point_id": "spawn-uuid-501",
      "zombie_type_ids": ["zombie-type-uuid-601"],
      "density": 3,
      "active_during_cycle": "night"
    }
  ]
}
```
 
#### List Sections
 
`GET /api/worlds/{world_id}/sections` Description: Returns all sections of the university and their unlock state.
 
Success Response (200 OK):
 
```json
{
  "world_id": "world-uuid-100",
  "sections": [
    {
      "section_id": "section-uuid-302",
      "name": "East Wing",
      "unlocked": false,
      "unlocked_by": null,
      "room_count": 6
    }
  ]
}
```
 
#### Unlock a Section
 
`POST /api/worlds/{world_id}/sections/unlock` Description: Administrative path for unlocking a section. The normal flow is the `exam_passed` event. Idempotent by `trigger_id`. Payload:
 
```json
{
  "trigger_id": "attempt-uuid-001",
  "course_id": "math_analysis"
}
```
 
Success Response (201 Created):
 
```json
{
  "section_id": "section-uuid-302",
  "name": "East Wing",
  "already_unlocked": false,
  "rooms": [
    {
      "room_id": "room-uuid-210",
      "name": "Chemistry Lab",
      "type": "laboratory",
      "floor": 4,
      "unlocked": true,
      "adjacent_room_ids": ["room-uuid-211"]
    }
  ]
}
```
 
Success Response (200 OK): the section was already unlocked, `already_unlocked` is `true`.
 
#### Service Status
 
`GET /api/status` Description: Health check.
 
Success Response (200 OK):
 
```json
{ "service": "world", "status": "ok", "uptime_seconds": 1234 }
```
 
---
 
## Events
 
#### `exam_passed`
 
Published by the Exam Service, consumed by the World Service. Applied idempotently by `attempt_id`, so a duplicated delivery generates no second section.
 
```json
{
  "event_id": "event-uuid-701",
  "attempt_id": "attempt-uuid-001",
  "player_id": "player-uuid-123",
  "course_id": "math_analysis",
  "exam_type": "final",
  "occurred_at": "2026-09-08T14:36:12Z"
}
```
 
#### `achievement_unlocked`
 
Published by the Exam Service, consumed by the Player Service, which applies the reward itself.
 
```json
{
  "event_id": "event-uuid-702",
  "player_id": "player-uuid-123",
  "achievement_id": "survived_the_pumpkin",
  "rewards": [
    { "type": "xp", "value": 500 }
  ],
  "occurred_at": "2026-09-08T14:36:12Z"
}
```
 
#### `section_unlocked`
 
Published by the World Service, consumed by the Resource Service (which creates the economy entries for the new nodes) and by the Game Service (which invalidates its map cache).
 
```json
{
  "event_id": "event-uuid-703",
  "world_id": "world-uuid-100",
  "section_id": "section-uuid-302",
  "trigger_id": "attempt-uuid-001",
  "rooms": [
    { "room_id": "room-uuid-210", "type": "laboratory" }
  ],
  "resource_nodes": [
    { "node_id": "node-uuid-410", "room_id": "room-uuid-210", "resource_type": "metal" }
  ],
  "occurred_at": "2026-09-08T14:37:02Z"
}
```
 

## Zombie Service
Owns zombie type definitions, per-type combat and behavior stats (health, speed, attack strength, perception radius), special abilities, the Professor/Tourist zombie categories, and custom zombie variants.

Does not own live/active zombie instances or their in-session behavior - Game Service does; Zombie Service exposes configuration data via query, and Game Service spawns and controls entities using it for the duration of a cycle.

Does not own spawn locations or spawn timing - Game Service does, in coordination with World Service's spawn points; Zombie Service only supplies which zombie types are eligible to be spawned when asked.

Does not own exam encounters triggered by Professor Zombies - Exam Service does; Game Service mediates the encounter and only reads zombie behavior data from Zombie Service beforehand.

## Resource Service
Owns resource types and quantities (wood, metal scraps, paper, food), which node/player they belong to, validation and application of resource changes, and consumption for barricading, upgrading, crafting and feeding Kiki.

Does not own the physical map or resource node placement - World Service does; Resource Service references nodes by ID and holds no geography of its own.

Does not own gathering action timers or the decision that an action has completed - Game Service does; Game Service raises a completion event once the timer finishes, and Resource Service validates and applies the resulting change idempotently, so reconnects or duplicate events can't award resources twice.

Does not own crafting recipes or the crafting operation itself - Crafting Service does; Crafting Service requests validation/deduction of the required resources from Resource Service when a recipe is executed.

Does not own new resource nodes created by map expansion - World Service decides the expansion; Resource Service consumes `SectionUnlocked` and creates the economy entries for the newly available nodes itself.
