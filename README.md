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

# Technologies and Communication patterns

## Player Service
### Go Programming language: 
\+ Great concurrency and synchronization model. Satisfies the requirement of having atomic trading.

\+ Goroutines enable small but frequent updates to the state in an concurrent context. Satisfies updating players Progression via calls from various services.

\+ Has battle tested libraries for working with Sqlite. Satisfies the requirement of having persistent storage for player's information.

