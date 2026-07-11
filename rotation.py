class RotationEngine:
    def __init__(self):
        self.rotations = {
            1: ["Meteor", "Push", "Buff", "Dash", "Fly", "Meteor", "Buff", "Push", "Fly", "Dash", "Meteor", "Push", "Dash", "Buff", "Fly"],
            2: ["Buff", "Charge", "Push", "Dash", "Meteor", "Fly", "Buff", "Dash", "Push", "Charge", "Meteor", "Fly"],
            3: ["Fly", "Meteor", "Push", "Dash", "Fly", "Buff", "Charge", "Meteor", "Push", "Dash", "Buff"],
            4: ["Meteor", "Buff", "Push", "Dash", "Charge", "Fly", "Meteor", "Push", "Buff", "Charge", "Dash", "Fly"]
        }
        self.phase = 1
        self.index = 0

    def set_phase(self, phase_num):
        if phase_num in self.rotations:
            if self.phase != phase_num:
                self.phase = phase_num
                self.index = 0
                return True
        return False

    def get_current_rotation(self):
        return self.rotations[self.phase]

    def get_next_moves(self, count=3):
        rotation = self.get_current_rotation()
        n = len(rotation)
        moves = []
        for i in range(count):
            moves.append(rotation[(self.index + i) % n])
        return moves

    def advance(self):
        rotation = self.get_current_rotation()
        self.index = (self.index + 1) % len(rotation)

    def reset(self):
        self.index = 0

    def process_voice_command(self, word):
        """
        Process a normalized voice command and return a status message if state changed.
        Returns: (state_changed, message)
        """
        w = word.lower().strip()
        
        # 1. Manual phase override commands
        if w in ["phase one", "p_one", "p1"]:
            if self.set_phase(1):
                return True, "Switched to Phase 1 manually"
        elif w in ["phase two", "p_two", "p2"]:
            if self.set_phase(2):
                return True, "Switched to Phase 2 manually"
        elif w in ["phase three", "p_three", "p3"]:
            if self.set_phase(3):
                return True, "Switched to Phase 3 manually"
        elif w in ["phase four", "p_four", "p4"]:
            if self.set_phase(4):
                return True, "Switched to Phase 4 manually"
        
        # 2. Reset command
        if w == "reset":
            self.reset()
            return True, "Rotation reset to start of current phase"

        # 3. Check if it matches a move in the current rotation (with stun skip up to 3 moves)
        rotation = self.get_current_rotation()
        n = len(rotation)
        
        # Check current expected, skip 1, skip 2, skip 3
        # Lookahead offset:
        # offset = 0 -> current expected
        # offset = 1 -> skip 1 (expected is at index + 1)
        # offset = 2 -> skip 2 (expected is at index + 2)
        # offset = 3 -> skip 3 (expected is at index + 3)
        for offset in range(4):
            candidate_idx = (self.index + offset) % n
            candidate_move = rotation[candidate_idx].lower()
            if w == candidate_move:
                # We found the matched move!
                # Set index to the next move after the matched one
                self.index = (candidate_idx + 1) % n
                if offset == 0:
                    return True, f"Advanced to next move: {rotation[self.index]}"
                else:
                    return True, f"Stun detected! Skipped {offset} move(s), advanced to: {rotation[self.index]}"

        # 4. Pattern-based next phase transition:
        # To prevent false jumps when at the start of a phase, we only trigger a pattern-based
        # next-phase transition if we are in the last 4 moves of the current phase cycle, OR
        # if the spoken move is unique to the next phases (like "charge" which isn't in P1).
        next_phase = self.phase + 1
        if next_phase <= 4:
            next_rotation = self.rotations[next_phase]
            is_near_end = (self.index >= n - 4)
            is_unique_trigger = (w == "charge" and self.phase == 1)
            
            if is_near_end or is_unique_trigger:
                # Check the first 3 moves of the next phase
                for i in range(min(3, len(next_rotation))):
                    if w == next_rotation[i].lower():
                        self.phase = next_phase
                        self.index = (i + 1) % len(next_rotation)
                        return True, f"Pattern matched next phase! Transitioned to Phase {self.phase}, next move: {next_rotation[self.index]}"

        return False, "Unrecognized command or out of skip range"
