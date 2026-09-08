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
