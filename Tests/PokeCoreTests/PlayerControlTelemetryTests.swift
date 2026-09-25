import XCTest
@testable import PokeCore
import PokeDataModel

@MainActor
extension PokeCoreTests {
    func testFieldStepLocksInputUntilMovementCooldownEnds() async throws {
        let runtime = try makeRepoRuntime()
        runtime.gameplayState = runtime.makeInitialGameplayState()
        runtime.scene = .field
        runtime.substate = "field"

        let before = runtime.currentSnapshot()
        XCTAssertTrue(before.inputReady)
        let start = before.field?.playerPosition

        var moved = false
        for button in [RuntimeButton.down, .up, .left, .right] {
            runtime.handle(button: button)
            if runtime.gameplayState?.playerPosition != start {
                moved = true
                break
            }
        }

        XCTAssertTrue(moved)
        XCTAssertFalse(runtime.currentSnapshot().inputReady)

        let unlocked = try await waitForSnapshot(runtime) { snapshot in
            snapshot.inputReady
        }
        XCTAssertTrue(unlocked.inputReady)
        XCTAssertEqual(unlocked.scene, .field)
        XCTAssertNotEqual(unlocked.field?.playerPosition, start)
    }

    func testOakIntroPresetFocusIsPublished() throws {
        let runtime = try makeRepoRuntime()
        runtime.oakIntroState = OakIntroState(
            phase: .namingPlayer,
            currentPageIndex: 0,
            enteredCharacters: [],
            playerName: nil,
            rivalName: nil,
            namePresetFocusedIndex: 0,
            isTypingCustomName: false
        )
        runtime.scene = .oakIntro
        runtime.substate = "oak_intro_naming_player"

        let snapshot = runtime.currentSnapshot()
        XCTAssertEqual(snapshot.oakIntro?.phase, "namingPlayer")
        XCTAssertEqual(snapshot.oakIntro?.presets, ["NEW NAME", "RED", "ASH", "JACK"])
        XCTAssertEqual(snapshot.oakIntro?.focusedIndex, 0)
        XCTAssertFalse(snapshot.oakIntro?.isTypingCustomName ?? true)
        XCTAssertTrue(snapshot.inputReady)

        runtime.handle(button: .down)
        XCTAssertEqual(runtime.currentSnapshot().oakIntro?.focusedIndex, 1)
        XCTAssertEqual(runtime.currentSnapshot().oakIntro?.presets, OakIntroState.playerNamePresets)
    }

    func testNicknamePromptFocusIsPublished() throws {
        let runtime = try makeRepoRuntime()
        runtime.gameplayState = runtime.makeInitialGameplayState()
        runtime.scene = .field
        runtime.substate = "field"
        runtime.beginNicknameConfirmation(
            speciesID: "SQUIRTLE",
            defaultName: "SQUIRTLE",
            completion: .returnToFieldAfterStarter
        )

        let snapshot = runtime.currentSnapshot()
        XCTAssertEqual(snapshot.nicknamePrompt?.speciesID, "SQUIRTLE")
        XCTAssertEqual(snapshot.nicknamePrompt?.defaultName, "SQUIRTLE")
        XCTAssertEqual(snapshot.nicknamePrompt?.focusedIndex, 0)
        XCTAssertTrue(snapshot.inputReady)

        runtime.handle(button: .down)
        XCTAssertEqual(runtime.currentSnapshot().nicknamePrompt?.focusedIndex, 1)
    }
}
