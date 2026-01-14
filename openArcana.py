import sqlite3

class Combatant:
    def __init__(self, id, name, initiative, max_hp, current_hp, ac, is_player, conditions=None, history=None):
        self.id = id
        self.name = name
        self.initiative = initiative
        self.max_hp = max_hp
        self.current_hp = current_hp
        self.ac = ac
        self.is_player = is_player
        self.conditions = conditions if conditions else []
        self.damage_history = history if history else []

    def __repr__(self):
        hp_str = f"{self.current_hp}/{self.max_hp}" if self.max_hp is not None else "N/A"
        ac_str = str(self.ac) if self.ac is not None else "N/A"
        return f"{self.name} (Init: {self.initiative}, HP: {hp_str}, AC: {ac_str})"

class InitiativeTracker:
    def __init__(self, db_path="./combat.db"):
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        self._init_db()
        self.current_index = 0
        self.round = 0
        self.combatants = []
        self.load_state()

    def _init_db(self):
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS combatants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                initiative INTEGER NOT NULL,
                max_hp INTEGER,
                current_hp INTEGER,
                ac INTEGER,
                is_player BOOLEAN NOT NULL
            )
        ''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS conditions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                combatant_id INTEGER,
                condition TEXT NOT NULL,
                duration INTEGER,
                FOREIGN KEY (combatant_id) REFERENCES combatants (id) ON DELETE CASCADE
            )
        ''')
        # Check if duration column exists, if not add it (for migration)
        self.cursor.execute("PRAGMA table_info(conditions)")
        columns = [column[1] for column in self.cursor.fetchall()]
        if "duration" not in columns:
            self.cursor.execute('ALTER TABLE conditions ADD COLUMN duration INTEGER')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                combatant_id INTEGER,
                type TEXT NOT NULL,
                amount INTEGER,
                damage_type TEXT,
                FOREIGN KEY (combatant_id) REFERENCES combatants (id) ON DELETE CASCADE
            )
        ''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS state (
                key TEXT PRIMARY KEY,
                value INTEGER
            )
        ''')
        self.cursor.execute('INSERT OR IGNORE INTO state (key, value) VALUES ("round", 0)')
        self.cursor.execute('INSERT OR IGNORE INTO state (key, value) VALUES ("current_index", 0)')
        self.conn.commit()

    def load_state(self):
        self.cursor.execute('SELECT value FROM state WHERE key="round"')
        self.round = self.cursor.fetchone()[0]
        self.cursor.execute('SELECT value FROM state WHERE key="current_index"')
        saved_index = self.cursor.fetchone()[0]
        
        # Keep track of who was current BEFORE we load and sort
        current_id = None
        if self.combatants and self.current_index < len(self.combatants):
            current_id = self.combatants[self.current_index].id
        
        self.combatants = []
        self.cursor.execute('SELECT id, name, initiative, max_hp, current_hp, ac, is_player FROM combatants')
        rows = self.cursor.fetchall()
        for row in rows:
            c_id = row[0]
            self.cursor.execute('SELECT condition, duration FROM conditions WHERE combatant_id=?', (c_id,))
            conditions = [{"name": r[0], "duration": r[1]} for r in self.cursor.fetchall()]
            
            self.cursor.execute('SELECT type, amount, damage_type FROM history WHERE combatant_id=?', (c_id,))
            history = [{"type": r[0], "amount": r[1], "damage_type": r[2]} for r in self.cursor.fetchall()]
            
            c = Combatant(c_id, row[1], row[2], row[3], row[4], row[5], bool(row[6]), conditions, history)
            self.combatants.append(c)

        self.sort_combatants(save=False)
        
        # If we had a current combatant, ensure we stay on them
        if current_id is not None:
            for i, c in enumerate(self.combatants):
                if c.id == current_id:
                    self.current_index = i
                    break
        else:
            # Otherwise use the saved index from DB
            self.current_index = saved_index

        # Ensure current_index is valid
        if self.combatants and self.current_index >= len(self.combatants):
            self.current_index = 0

    def save_state(self):
        self.cursor.execute('UPDATE state SET value=? WHERE key="round"', (self.round,))
        self.cursor.execute('UPDATE state SET value=? WHERE key="current_index"', (self.current_index,))
        self.conn.commit()

    def add_combatant(self, name, initiative, hp, ac, is_player):
        if not self.combatants:
            self.round = 1
            self.current_index = 0
            self.save_state()
        else:
            # Before adding, ensure current_index is saved so load_state picks it up
            self.save_state()
            
        self.cursor.execute('''
            INSERT INTO combatants (name, initiative, max_hp, current_hp, ac, is_player)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (name, initiative, hp, hp, ac, is_player))
        c_id = self.cursor.lastrowid
        self.conn.commit()
        self.load_state()

    def remove_combatant(self, name):
        self.cursor.execute('DELETE FROM combatants WHERE LOWER(name)=LOWER(?)', (name,))
        self.conn.commit()
        self.load_state()
        if not self.combatants:
            self.round = 0
            self.current_index = 0
            self.save_state()

    def clear_combatants(self):
        self.cursor.execute('DELETE FROM combatants')
        self.conn.commit()
        self.load_state()
        if not self.combatants:
            self.round = 0
            self.current_index = 0
            self.save_state()

    def sort_combatants(self, save=True):
        # Keep track of who is current before sorting
        current_id = None
        if self.combatants and self.current_index < len(self.combatants):
            current_id = self.combatants[self.current_index].id
            
        self.combatants.sort(key=lambda x: (x.initiative, x.name), reverse=True)
        
        # Restore current_index to the same person
        if current_id is not None:
            for i, c in enumerate(self.combatants):
                if c.id == current_id:
                    self.current_index = i
                    break
                    
        if save:
            self.save_state()

    def next_turn(self):
        if not self.combatants:
            return
        
        # Before moving to next turn, decrement conditions for the current combatant
        current_combatant = self.combatants[self.current_index]
        self.cursor.execute('SELECT id, condition, duration FROM conditions WHERE combatant_id=?', (current_combatant.id,))
        conds = self.cursor.fetchall()
        for c_id, c_name, c_duration in conds:
            if c_duration is not None:
                new_duration = c_duration - 1
                if new_duration <= 0:
                    self.cursor.execute('DELETE FROM conditions WHERE id=?', (c_id,))
                else:
                    self.cursor.execute('UPDATE conditions SET duration=? WHERE id=?', (new_duration, c_id))
        
        # Reload state to ensure we have latest data (e.g. if conditions were deleted)
        # This will also ensure our current_index is valid for the current person
        self.load_state()
        
        self.current_index += 1
        if self.current_index >= len(self.combatants):
            self.current_index = 0
            self.round += 1
        self.conn.commit()
        # Save state to persist the move to next turn
        self.save_state()

    def take_damage(self, name, amount, damage_type):
        for c in self.combatants:
            if c.name.lower() == name.lower():
                if c.max_hp is not None:
                    c.current_hp -= amount
                    if c.current_hp < 0: c.current_hp = 0
                    self.cursor.execute('UPDATE combatants SET current_hp=? WHERE id=?', (c.current_hp, c.id))

                self.cursor.execute('INSERT INTO history (combatant_id, type, amount, damage_type) VALUES (?, ?, ?, ?)',
                                    (c.id, "damage", amount, damage_type))
                self.conn.commit()
                self.load_state()
                return True
        return False

    def heal(self, name, amount):
        for c in self.combatants:
            if c.name.lower() == name.lower():
                if c.max_hp is not None:
                    c.current_hp += amount
                    if c.current_hp > c.max_hp: c.current_hp = c.max_hp
                    self.cursor.execute('UPDATE combatants SET current_hp=? WHERE id=?', (c.current_hp, c.id))

                self.cursor.execute('INSERT INTO history (combatant_id, type, amount) VALUES (?, ?, ?)',
                                    (c.id, "heal", amount))
                self.conn.commit()
                self.load_state()
                return True
        return False

    def add_condition(self, name, condition, duration=None):
        for c in self.combatants:
            if c.name.lower() == name.lower():
                self.cursor.execute('INSERT INTO conditions (combatant_id, condition, duration) VALUES (?, ?, ?)', (c.id, condition, duration))
                self.conn.commit()
                self.load_state()
                return True
        return False

    def remove_condition(self, name, condition):
        for c in self.combatants:
            if c.name.lower() == name.lower():
                self.cursor.execute('DELETE FROM conditions WHERE combatant_id=? AND LOWER(condition)=LOWER(?)', (c.id, condition))
                self.conn.commit()
                self.load_state()
                return True
        return False

    def display(self):
        print(f"\n--- Round {self.round} ---")
        print(f"{'#':<3} {'Name':<15} {'Init':<5} {'HP':<12} {'AC':<4} {'Type':<8} {'Conditions'}")
        print("-" * 75)
        for i, c in enumerate(self.combatants):
            marker = ">>" if i == self.current_index else "  "
            hp_str = f"{c.current_hp}/{c.max_hp}" if c.max_hp is not None else "N/A"
            ac_str = str(c.ac) if c.ac is not None else "N/A"
            c_type = "Player" if c.is_player else "Monster"
            
            cond_list = []
            for cond in c.conditions:
                if cond['duration'] is not None:
                    cond_list.append(f"{cond['name']}({cond['duration']}r)")
                else:
                    cond_list.append(cond['name'])
            conds = ", ".join(cond_list)
            
            hp_visual = ""
            if c.max_hp is not None and c.max_hp > 0:
                hp_percent = c.current_hp / c.max_hp
                if hp_percent <= 0: hp_visual = "[DEAD]"
                elif hp_percent < 0.25: hp_visual = "[CRIT]"
                elif hp_percent < 0.5: hp_visual = "[BLD]"
                
            print(f"{marker:<3} {c.name:<15} {c.initiative:<5} {hp_str:<12} {ac_str:<4} {c_type:<8} {hp_visual} {conds}")
        print("-" * 75)
