import Foundation
import PokeDataModel

private struct ResolvedScriptMovementActor {
    let actorID: String
    let path: [FacingDirection]
    let startPoint: TilePoint?
}

extension GameRuntime {
    func beginScriptedPlayerMovement(_ path: [FacingDirection]) {
        beginScriptedMovement(.init(kind: .fixedPath, actors: [.init(actorID: "player", path: path)]))
    }

    func beginScriptedMovement(_ movement: ScriptMovementManifest) {
        clearHeldFieldDirections()
        fieldMovementTask?.cancel()
        fieldMovementTask = nil
        idleMovementTask?.cancel()
        idleMovementTask = nil
        scriptedMovementTask?.cancel()
        scriptedMovementTask = Task { [weak self] in
            await self?.runScriptedMovement(movement)
        }
    }

    func beginFieldMovementCooldown() {
        fieldMovementTask?.cancel()
        fieldMovementTask = Task { [weak self] in
            guard let self else { return }
            await self.sleep(seconds: self.fieldStepDuration)
            guard Task.isCancelled == false else { return }
            self.fieldMovementTask = nil
            _ = self.consumeHeldFieldDirectionIfPossible()
            self.publishSnapshot()
        }
    }

    func runScriptedPlayerMovement(_ path: [FacingDirection]) async {
        await runScriptedMovement(.init(kind: .fixedPath, actors: [.init(actorID: "player", path: path)]))
    }

    func runScriptedMovement(_ movement: ScriptMovementManifest) async {
        defer {
            scriptedMovementTask = nil
            publishSnapshot()
        }

        let actors = resolvedActors(for: movement)
        guard actors.isEmpty == false else {
            runActiveScript()
            publishSnapshot()
            return
        }

        await animateActors(actors, mode: .scripted)
        guard Task.isCancelled == false else { return }
        runActiveScript()
        publishSnapshot()
    }

    func animatePlayerMovement(path: [FacingDirection]) async {
        guard path.isEmpty == false else { return }
        await animateActors([.init(actorID: "player", path: path, startPoint: nil)], mode: .scripted)
    }

    func animateObjectMovement(actorID: String, path: [FacingDirection]) async {
        guard path.isEmpty == false else { return }
        await animateActors([.init(actorID: actorID, path: path, startPoint: nil)], mode: .scripted)
    }

    func refreshIdleMovementScheduling() {
        guard canRunIdleMovement else {
            idleMovementTask?.cancel()
            idleMovementTask = nil
            return
        }
        guard idleMovementTask == nil else { return }
        idleMovementTask = Task { [weak self] in
            await self?.runIdleMovementLoop()
        }
    }

    var canRunIdleMovement: Bool {
        scene == .field &&
            dialogueState == nil &&
            gameplayState?.battle == nil &&
            fieldTransitionState == nil &&
            scriptedMovementTask == nil &&
            trainerEngagementTask == nil
    }

    func runIdleMovementLoop() async {
        defer {
            idleMovementTask = nil
        }

        while Task.isCancelled == false {
            await sleep(seconds: idleMovementInterval)
            guard Task.isCancelled == false else { return }
            await performIdleMovementCycle()
        }
    }

    func performIdleMovementCycle() async {
        guard canRunIdleMovement, var gameplayState, let map = currentMapManifest else { return }
        let visibleWalkers = map.objects
            .filter { object in
                object.movementBehavior.idleMode == .walk &&
                    (gameplayState.objectStates[object.id]?.visible ?? object.visibleByDefault) &&
                    gameplayState.objectStates[object.id]?.movementMode == nil
            }
            .sorted { $0.id < $1.id }

        guard visibleWalkers.isEmpty == false else { return }

        var occupiedTiles = occupiedTileSet(excludingObjectIDs: [], excludingPlayer: false)
        var reservedTiles: Set<TilePoint> = []
        var plannedActors: [ResolvedScriptMovementActor] = []

        for object in visibleWalkers {
            guard let objectState = gameplayState.objectStates[object.id] else { continue }
            let directions = object.movementBehavior.axis.allowedDirections
            guard directions.isEmpty == false else { continue }

            let startIndex = objectState.idleStepIndex % directions.count
            var chosenDirection: FacingDirection?
            var chosenDestination: TilePoint?

            for offset in 0..<directions.count {
                let direction = directions[(startIndex + offset) % directions.count]
                let next = translated(objectState.position, by: direction)
                guard isWithinIdleBounds(next, behavior: object.movementBehavior) else { continue }
                guard canActorOccupy(
                    next,
                    from: objectState.position,
                    in: map,
                    facing: direction,
                    occupiedTiles: occupiedTiles.subtracting([objectState.position]),
                    reservedTiles: reservedTiles
                ) else {
                    continue
                }
                chosenDirection = direction
                chosenDestination = next
                break
            }

            gameplayState.objectStates[object.id]?.idleStepIndex += 1

            guard let chosenDirection, let chosenDestination else { continue }
            reservedTiles.insert(chosenDestination)
            occupiedTiles.remove(objectState.position)
            occupiedTiles.insert(chosenDestination)
            plannedActors.append(.init(actorID: object.id, path: [chosenDirection], startPoint: nil))
        }

        self.gameplayState = gameplayState
        guard plannedActors.isEmpty == false else { return }
        await animateActors(plannedActors, mode: .idle)
    }

    var idleMovementInterval: TimeInterval {
        validationMode ? 0.05 : 0.32
    }

    var fieldStepDuration: TimeInterval {
        fieldAnimationStepDuration
    }

    func sleep(seconds: TimeInterval) async {
        guard seconds > 0 else { return }
        try? await Task.sleep(nanoseconds: UInt64(seconds * 1_000_000_000))
    }

    func isWithinIdleBounds(_ point: TilePoint, behavior: ObjectMovementBehavior) -> Bool {
        let dx = abs(point.x - behavior.home.x)
        let dy = abs(point.y - behavior.home.y)
        return max(dx, dy) <= behavior.maxDistanceFromHome
    }
    private func animateActors(_ actors: [ResolvedScriptMovementActor], mode: ActorMovementMode) async {
        guard actors.isEmpty == false else { return }
        applyMovementStartPointsIfNeeded(actors)
        let maxPathLength = actors.map { $0.path.count }.max() ?? 0
        guard maxPathLength > 0 else {
            clearMovementModes(for: actors)
            publishSnapshot()
            return
        }

        for stepIndex in 0..<maxPathLength {
            guard Task.isCancelled == false,
                  var gameplayState,
                  let map = currentMapManifest else {
                clearMovementModes(for: actors)
                return
            }

            let movingObjectIDs = Set(actors.lazy.filter { $0.actorID != "player" }.map(\.actorID))
            var occupiedTiles = occupiedTileSet(
                excludingObjectIDs: movingObjectIDs,
                excludingPlayer: actors.contains { $0.actorID == "player" }
            )
            var reservedTiles: Set<TilePoint> = []

            for actor in actors where actor.path.indices.contains(stepIndex) {
                let direction = actor.path[stepIndex]
                if actor.actorID == "player" {
                    let current = gameplayState.playerPosition
                    let next = translated(current, by: direction)
                    guard canActorOccupy(
                        next,
                        from: current,
                        in: map,
                        facing: direction,
                        occupiedTiles: occupiedTiles,
                        reservedTiles: reservedTiles
                    ) else {
                        continue
                    }
                    gameplayState.facing = direction
                    gameplayState.playerPosition = next
                    occupiedTiles.insert(next)
                    reservedTiles.insert(next)
                } else if var objectState = gameplayState.objectStates[actor.actorID] {
                    let current = objectState.position
                    let next = translated(current, by: direction)
                    guard canActorOccupy(
                        next,
                        from: current,
                        in: map,
                        facing: direction,
                        occupiedTiles: occupiedTiles,
                        reservedTiles: reservedTiles
                    ) else {
                        objectState.facing = direction
                        gameplayState.objectStates[actor.actorID] = objectState
                        continue
                    }
                    objectState.facing = direction
                    objectState.position = next
                    objectState.movementMode = mode
                    gameplayState.objectStates[actor.actorID] = objectState
                    occupiedTiles.insert(next)
                    reservedTiles.insert(next)
                }
            }

            self.gameplayState = gameplayState
            publishSnapshot()
            await sleep(seconds: fieldStepDuration)
        }

        clearMovementModes(for: actors)
        publishSnapshot()
    }

}

private extension GameRuntime {
    func resolvedActors(for movement: ScriptMovementManifest) -> [ResolvedScriptMovementActor] {
        guard let gameplayState, let map = currentMapManifest else { return [] }
        let selectedVariant = movement.variants.first {
            $0.conditions.allSatisfy { conditionMatches($0, blockedMoveFacing: nil) }
        }

        let actors = selectedVariant?.actors ?? movement.actors
        let startPoint = selectedVariant?.point

        switch movement.kind {
        case .pathToPlayerAdjacent:
            guard let actorID = actors.first?.actorID else {
                return []
            }
            let target = TilePoint(
                x: gameplayState.playerPosition.x + (movement.targetPlayerOffset?.x ?? 0),
                y: gameplayState.playerPosition.y + (movement.targetPlayerOffset?.y ?? 0)
            )
            return resolvedPathActor(
                actorID: actorID,
                target: target,
                startPoint: startPoint,
                gameplayState: gameplayState,
                map: map
            )
        case .pathToObjectOffset:
            guard let actorID = actors.first?.actorID,
                  let targetObjectID = movement.targetObjectID,
                  let targetObject = gameplayState.objectStates[targetObjectID] else {
                return []
            }
            let target = TilePoint(
                x: targetObject.position.x + (movement.targetObjectOffset?.x ?? 0),
                y: targetObject.position.y + (movement.targetObjectOffset?.y ?? 0)
            )
            return resolvedPathActor(
                actorID: actorID,
                target: target,
                startPoint: startPoint,
                gameplayState: gameplayState,
                map: map
            )
        case .fixedPath, .palletEscort, .rivalStarterPickup:
            return actors.map { ResolvedScriptMovementActor(actorID: $0.actorID, path: $0.path, startPoint: startPoint) }
        }
    }

    func resolvedPathActor(
        actorID: String,
        target: TilePoint,
        startPoint: TilePoint?,
        gameplayState: GameplayState,
        map: MapManifest
    ) -> [ResolvedScriptMovementActor] {
        guard actorID != "player",
              let objectState = gameplayState.objectStates[actorID],
              let path = shortestPath(
                  from: objectState.position,
                  to: target,
                  in: map,
                  ignoringObjectID: actorID
              ) else {
            return []
        }

        return [.init(actorID: actorID, path: path, startPoint: startPoint)]
    }

    func applyMovementStartPointsIfNeeded(_ actors: [ResolvedScriptMovementActor]) {
        guard var gameplayState else { return }
        var didChangeState = false

        for actor in actors {
            guard let startPoint = actor.startPoint, actor.actorID != "player" else { continue }
            if gameplayState.objectStates[actor.actorID]?.position != startPoint {
                gameplayState.objectStates[actor.actorID]?.position = startPoint
                didChangeState = true
            }
        }

        if didChangeState {
            self.gameplayState = gameplayState
            publishSnapshot()
        }
    }

    func clearMovementModes(for actors: [ResolvedScriptMovementActor]) {
        guard var gameplayState else { return }
        for actor in actors where actor.actorID != "player" {
            gameplayState.objectStates[actor.actorID]?.movementMode = nil
        }
        self.gameplayState = gameplayState
    }
}
