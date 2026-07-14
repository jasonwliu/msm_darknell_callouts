class RotationEngine:
    def __init__(self):
        self.rotations = {
            1: ["Meteor", "Push", "Buff", "Dash", "Dive", "Meteor", "Buff", "Push", "Dive", "Dash", "Meteor", "Push", "Dash", "Buff", "Dive"],
            2: ["Dive", "Buff", "Charge", "Push", "Dash", "Meteor", "Dive", "Buff", "Dash", "Push", "Charge", "Meteor"],
            3: ["Dive", "Meteor", "Push", "Dash", "Dive", "Buff", "Charge", "Meteor", "Push", "Dash", "Buff"],
            4: ["Meteor", "Buff", "Push", "Dash", "Charge", "Dive", "Meteor", "Push", "Buff", "Charge", "Dash", "Dive"]
        }
        self.phase = 1
        self.index = 0
        self.voice_history = []
        self.executed_history = []
        self.stun_flag = False

    def set_phase(self, phase_num):
        if phase_num in self.rotations:
            if self.phase != phase_num:
                self.phase = phase_num
                self.index = 0
                self.voice_history.clear()
                self.executed_history.clear()
                self.stun_flag = False
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
        self.voice_history.clear()
        self.executed_history.clear()
        self.stun_flag = False

    def sync_by_sequence(self):
        """
        Scan the current rotation to find if the sequence of recent voice commands
        matches any part of the rotation. Sync index to the move following the match.
        """
        rotation = self.get_current_rotation()
        n = len(rotation)
        history = [m.lower() for m in self.voice_history]
        
        # Try length 3 first, then length 2
        for k in [3, 2]:
            if len(history) < k:
                continue
            seq = history[-k:]
            matches = []
            for i in range(n):
                match = True
                for j in range(k):
                    if rotation[(i + j) % n].lower() != seq[j]:
                        match = False
                        break
                if match:
                    matches.append(i)
                    
            if len(matches) == 1:
                # Unique match found! Sync index
                self.index = (matches[0] + k) % n
                self.voice_history.clear()
                return True, f"Sequence matched! Synced to next move: {rotation[self.index]}"
            elif len(matches) > 1:
                # Multiple matches. Find the one closest to current index (minimal positive distance)
                best_idx = None
                min_dist = float('inf')
                for start_idx in matches:
                    next_idx = (start_idx + k) % n
                    dist = (next_idx - self.index) % n
                    if dist < min_dist:
                        min_dist = dist
                        best_idx = next_idx
                if best_idx is not None:
                    self.index = best_idx
                    self.voice_history.clear()
                    return True, f"Sequence matched (closest)! Synced to next move: {rotation[self.index]}"
        return False, None

    def process_voice_command(self, word):
        """
        Process a normalized voice command and return a status message if state changed.
        Returns: (state_changed, message)
        """
        w = word.lower().strip()
        if w in ["shock", "shockwave"]:
            w = "charge"
        
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

        # 3. Handle stun/stunned flag
        if w in ["stun", "stunned"]:
            self.stun_flag = True
            return True, "Stun skip mode enabled. Speak the move you see next."

        # Check if it is a valid move name
        valid_moves = {"meteor", "push", "buff", "dash", "dive", "charge"}
        if w not in valid_moves:
            return False, "Unrecognized command or out of skip range"

        rotation = self.get_current_rotation()
        n = len(rotation)

        # 4. Check for recently executed move filter (lookahead repeat suppression)
        # We only check this if the spoken word is NOT the immediate next expected move.
        is_next_move = (w == rotation[self.index].lower())
        if not is_next_move and not self.stun_flag:
            if w in self.executed_history:
                return False, f"Ignored repeat: '{w}' matches a recently executed move"

        # Append to history
        self.voice_history.append(w)
        if len(self.voice_history) > 3:
            self.voice_history.pop(0)

        # 5. Try sequence-based resynchronization
        synced, msg = self.sync_by_sequence()
        if synced:
            synced_move = rotation[(self.index - 1) % n].lower()
            self.executed_history.append(synced_move)
            if len(self.executed_history) > 3:
                self.executed_history.pop(0)
            self.stun_flag = False
            return True, msg

        # 6. Immediate match (offset == 0)
        if is_next_move:
            self.executed_history.append(w)
            if len(self.executed_history) > 3:
                self.executed_history.pop(0)
            self.index = (self.index + 1) % n
            self.stun_flag = False
            return True, f"Advanced to next move: {rotation[self.index]}"

        # 7. Fallback to standard single-move skip lookahead (scan the entire phase) ONLY if stun flag is active!
        if self.stun_flag:
            for offset in range(1, n):
                candidate_idx = (self.index + offset) % n
                candidate_move = rotation[candidate_idx].lower()
                if w == candidate_move:
                    self.executed_history.append(w)
                    if len(self.executed_history) > 3:
                        self.executed_history.pop(0)
                    self.index = (candidate_idx + 1) % n
                    self.stun_flag = False
                    return True, f"Stun detected! Skipped {offset} move(s), advanced to: {rotation[self.index]}"

        # 8. Pattern-based next phase transition
        next_phase = self.phase + 1
        if next_phase <= 4:
            next_rotation = self.rotations[next_phase]
            is_near_end = (self.index >= n - 4)
            is_unique_trigger = (w == "charge" and self.phase == 1)
            
            if is_near_end or is_unique_trigger:
                for i in range(min(3, len(next_rotation))):
                    if w == next_rotation[i].lower():
                        self.phase = next_phase
                        self.index = (i + 1) % len(next_rotation)
                        self.voice_history.clear()
                        self.executed_history.clear()
                        self.executed_history.append(w)
                        self.stun_flag = False
                        return True, f"Pattern matched next phase! Transitioned to Phase {self.phase}, next move: {next_rotation[self.index]}"

        return False, "Unrecognized command or out of skip range"



