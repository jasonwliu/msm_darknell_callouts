from rotation import RotationEngine

def test_initial_state():
    engine = RotationEngine()
    assert engine.phase == 1
    assert engine.index == 0
    assert engine.get_next_moves() == ["Meteor", "Push", "Buff"]

def test_normal_advance():
    engine = RotationEngine()
    engine.advance()
    assert engine.index == 1
    assert engine.get_next_moves() == ["Push", "Buff", "Dash"]

def test_voice_command_normal():
    engine = RotationEngine()
    changed, msg = engine.process_voice_command("meteor")
    assert changed
    assert engine.index == 1
    assert engine.get_next_moves() == ["Push", "Buff", "Dash"]

def test_voice_command_skip_1():
    engine = RotationEngine()
    # next expected: Meteor, then Push
    # Let's say "stun", then "push" (skips Meteor, i.e. 1 skip)
    changed_stun, msg_stun = engine.process_voice_command("stun")
    assert changed_stun
    assert engine.stun_flag == True
    
    changed, msg = engine.process_voice_command("push")
    assert changed
    assert "Stun detected" in msg
    assert engine.stun_flag == False
    assert engine.index == 2  # next move is Buff
    assert engine.get_next_moves() == ["Buff", "Dash", "Dive"]

def test_voice_command_skip_3():
    engine = RotationEngine()
    # next expected: Meteor, Push, Buff, Dash, Fly
    # Let's say "stunned", then "dash" (skips Meteor, Push, Buff - i.e. 3 skips)
    changed_stun, msg_stun = engine.process_voice_command("stunned")
    assert changed_stun
    assert engine.stun_flag == True
    
    changed, msg = engine.process_voice_command("dash")
    assert changed
    assert "Stun detected" in msg
    assert engine.stun_flag == False
    assert engine.index == 4  # next move is Dive
    assert engine.get_next_moves()[0] == "Dive"

def test_voice_command_out_of_order_without_stun_ignored():
    engine = RotationEngine()
    # next expected: Meteor
    # speak: "push" (which is index 1, not index 0, and no stun mode)
    # it should not skip and should remain at index 0
    changed, msg = engine.process_voice_command("push")
    assert not changed
    assert engine.index == 0

def test_voice_command_reset():
    engine = RotationEngine()
    engine.advance()
    engine.advance()
    changed, msg = engine.process_voice_command("reset")
    assert changed
    assert engine.index == 0

def test_voice_command_manual_phase():
    engine = RotationEngine()
    changed, msg = engine.process_voice_command("p2")
    assert changed
    assert engine.phase == 2
    assert engine.index == 0
    assert engine.get_next_moves()[0] == "Dive"

def test_phase2_transition_fly_out_of_sequence():
    engine = RotationEngine()
    # We are in Phase 1 (index 0). Next expected move is Meteor.
    # User says "dive" (Fly) which is out of sequence.
    # It should NOT transition to Phase 2.
    changed, msg = engine.process_voice_command("dive")
    assert not changed
    assert engine.phase == 1
    assert engine.index == 0

def test_phase2_transition_fly_in_sequence_not_end():
    engine = RotationEngine()
    # Let's advance to index 4 in Phase 1 (expected move: Dive)
    # P1 rotation: ["Meteor", "Push", "Buff", "Dash", "Dive", ...]
    engine.process_voice_command("meteor")
    engine.process_voice_command("push")
    engine.process_voice_command("buff")
    engine.process_voice_command("dash")
    assert engine.index == 4
    assert engine.get_next_moves()[0] == "Dive"
    
    # User says "dive" which is in sequence
    changed, msg = engine.process_voice_command("dive")
    assert changed
    # It should NOT transition to Phase 2 because it was in sequence and not at the end
    assert engine.phase == 1
    assert engine.index == 5
    assert engine.get_next_moves()[0] == "Meteor"

def test_phase2_transition_fly_in_sequence_end():
    engine = RotationEngine()
    # Let's advance to index 14 in Phase 1 (expected move: Dive)
    # P1 rotation: ["Meteor", "Push", "Buff", "Dash", "Dive", "Meteor", "Buff", "Push", "Dive", "Dash", "Meteor", "Push", "Dash", "Buff", "Dive"]
    # Let's manually set index to 14 to make it simple
    engine.index = 14
    assert engine.get_next_moves()[0] == "Dive"
    
    # User says "dive" (Fly) which is in sequence but at the end of the phase
    changed, msg = engine.process_voice_command("dive")
    assert changed
    # It should NOT transition to Phase 2, but instead loop back to index 0 of Phase 1
    assert engine.phase == 1
    assert engine.index == 0
    assert engine.get_next_moves()[0] == "Meteor"

def test_phase2_transition_manual():
    engine = RotationEngine()
    changed, msg = engine.process_voice_command("p2")
    assert changed
    assert engine.phase == 2
    assert engine.index == 0

def test_phase2_no_transition_on_charge():
    engine = RotationEngine()
    # Saying "ultimate" should not transition to Phase 2 anymore
    changed, msg = engine.process_voice_command("ultimate")
    assert not changed
    assert engine.phase == 1
    assert engine.index == 0

def test_voice_command_repeat_ignore():
    engine = RotationEngine()
    # Phase 1 sequence starting: Meteor, Push, Buff, Dash, Dive, Meteor...
    # Say meteor: advances index to 1 ("Push")
    changed, msg = engine.process_voice_command("meteor")
    assert changed
    assert engine.index == 1
    
    # Say meteor again: it's in the past 3 executed moves (Index 0 is Meteor).
    # Since it's a repeat, it should be ignored.
    changed, msg = engine.process_voice_command("meteor")
    assert not changed
    assert "Ignored repeat" in msg
    assert engine.index == 1

def test_voice_command_sequence_sync():
    engine = RotationEngine()
    # speak: "buff", "push"
    changed1, msg1 = engine.process_voice_command("buff")
    assert not changed1  # Ignored as a single out-of-order move
    assert engine.index == 0  # Index remains at start
    
    changed2, msg2 = engine.process_voice_command("push")
    # "buff" then "push" uniquely matches Phase 1 index 6-7 ("Buff", "Push").
    # It should sync index to (7 + 1) = 8 ("Dive").
    assert changed2
    assert engine.index == 8
    assert "Sequence matched" in msg2

def test_voice_command_dive_into_meteor_sync():
    engine = RotationEngine()
    # Next expected is Meteor. User says "dash", "dive", then "meteor"
    # "dash" -> "dive" is a unique sequence in Phase 1 (index 3-4), syncing to index 5 ("Meteor")
    changed1, msg1 = engine.process_voice_command("dash")
    assert not changed1
    assert engine.index == 0
    
    changed2, msg2 = engine.process_voice_command("dive")
    assert changed2
    assert engine.index == 5
    assert "Sequence matched" in msg2
    
    changed3, msg3 = engine.process_voice_command("meteor")
    assert changed3
    assert engine.index == 6
    assert "Advanced to next" in msg3

def test_voice_command_shock_mappings():
    engine = RotationEngine()
    # Go to Phase 2
    engine.set_phase(2)
    # Next expected is Dive (index 0), then Buff (index 1), then Ultimate (index 2).
    # Say "dive" (mapped from "fly"/"dive"): advances to 1 ("Buff")
    changed1, msg1 = engine.process_voice_command("dive")
    assert changed1
    # Say "buff": advances to 2 ("Ultimate")
    changed2, msg2 = engine.process_voice_command("buff")
    assert changed2
    
    # Try calling "shock" or "shockwave" (mapped to "ultimate"). Next is "Ultimate".
    changed3, msg3 = engine.process_voice_command("shock")
    assert changed3
    assert engine.index == 3  # next is Push
    assert engine.get_next_moves()[0] == "Push"


def test_voice_command_stun_skip_with_history():
    engine = RotationEngine()
    engine.set_phase(2)
    
    # 1. Process "dive" (advances index to 1)
    engine.process_voice_command("dive")
    # 2. Process "buff" (advances index to 2)
    engine.process_voice_command("buff")
    
    # Next expected is index 2 ("Ultimate"). History contains "dive" and "buff".
    # Say "stun", then "dive" (skips Ultimate, Push, Dash, Meteor to go to index 6 "Dive")
    changed_stun, msg_stun = engine.process_voice_command("stun")
    assert changed_stun
    assert engine.stun_flag == True
    
    changed, msg = engine.process_voice_command("dive")
    assert changed
    assert "Stun detected" in msg
    assert engine.index == 7  # next expected is index 7 ("Buff")


def test_phase3_dives():
    engine = RotationEngine()
    engine.set_phase(3)
    # P3 rotation: ["Short Dive", "Meteor", "Push", "Dash", "Long Dive", "Buff", "Ultimate", "Meteor", "Push", "Dash", "Buff"]
    
    # 1. Expected next is "Short Dive" (index 0). Saying "short dive" should match.
    assert engine.get_next_moves()[0] == "Short Dive"
    changed, msg = engine.process_voice_command("short dive")
    assert changed
    assert engine.index == 1
    assert engine.get_next_moves()[0] == "Meteor"
    
    # Let's reset phase 3
    engine = RotationEngine()
    engine.set_phase(3)
    # 2. Saying general "dive" should also match the expected "Short Dive"
    changed, msg = engine.process_voice_command("dive")
    assert changed
    assert engine.index == 1
    
    # 3. Advance to index 4 ("Long Dive")
    # moves: index 1 ("Meteor"), index 2 ("Push"), index 3 ("Dash")
    engine.process_voice_command("meteor")
    engine.process_voice_command("push")
    engine.process_voice_command("dash")
    assert engine.get_next_moves()[0] == "Long Dive"
    
    # Saying general "dive" should match the expected "Long Dive"
    changed, msg = engine.process_voice_command("dive")
    assert changed
    assert engine.index == 5
    assert engine.get_next_moves()[0] == "Buff"
    
    # Reset and test saying "long dive" on index 4
    engine = RotationEngine()
    engine.set_phase(3)
    engine.process_voice_command("dive") # index 0
    engine.process_voice_command("meteor") # index 1
    engine.process_voice_command("push") # index 2
    engine.process_voice_command("dash") # index 3
    assert engine.get_next_moves()[0] == "Long Dive"
    changed, msg = engine.process_voice_command("long dive")
    assert changed
    assert engine.index == 5


