import sys
import sqlite3
import os

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

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
        self.round = 1
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
                FOREIGN KEY (combatant_id) REFERENCES combatants (id) ON DELETE CASCADE
            )
        ''')
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
        self.cursor.execute('INSERT OR IGNORE INTO state (key, value) VALUES ("round", 1)')
        self.cursor.execute('INSERT OR IGNORE INTO state (key, value) VALUES ("current_index", 0)')
        self.conn.commit()

    def load_state(self):
        self.cursor.execute('SELECT value FROM state WHERE key="round"')
        self.round = self.cursor.fetchone()[0]
        self.cursor.execute('SELECT value FROM state WHERE key="current_index"')
        self.current_index = self.cursor.fetchone()[0]
        
        self.combatants = []
        self.cursor.execute('SELECT id, name, initiative, max_hp, current_hp, ac, is_player FROM combatants')
        rows = self.cursor.fetchall()
        for row in rows:
            c_id = row[0]
            self.cursor.execute('SELECT condition FROM conditions WHERE combatant_id=?', (c_id,))
            conditions = [r[0] for r in self.cursor.fetchall()]
            
            self.cursor.execute('SELECT type, amount, damage_type FROM history WHERE combatant_id=?', (c_id,))
            history = [{"type": r[0], "amount": r[1], "damage_type": r[2]} for r in self.cursor.fetchall()]
            
            c = Combatant(c_id, row[1], row[2], row[3], row[4], row[5], bool(row[6]), conditions, history)
            self.combatants.append(c)
        self.sort_combatants(save=False)

    def save_state(self):
        self.cursor.execute('UPDATE state SET value=? WHERE key="round"', (self.round,))
        self.cursor.execute('UPDATE state SET value=? WHERE key="current_index"', (self.current_index,))
        self.conn.commit()

    def add_combatant(self, name, initiative, hp, ac, is_player):
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

    def sort_combatants(self, save=True):
        self.combatants.sort(key=lambda x: (x.initiative, x.name), reverse=True)
        if save:
            self.save_state()

    def next_turn(self):
        if not self.combatants:
            return
        self.current_index += 1
        if self.current_index >= len(self.combatants):
            self.current_index = 0
            self.round += 1
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

    def add_condition(self, name, condition):
        for c in self.combatants:
            if c.name.lower() == name.lower():
                self.cursor.execute('INSERT INTO conditions (combatant_id, condition) VALUES (?, ?)', (c.id, condition))
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
            conds = ", ".join(c.conditions) if c.conditions else ""
            
            hp_visual = ""
            if c.max_hp is not None and c.max_hp > 0:
                hp_percent = c.current_hp / c.max_hp
                if hp_percent <= 0: hp_visual = "[DEAD]"
                elif hp_percent < 0.25: hp_visual = "[CRIT]"
                elif hp_percent < 0.5: hp_visual = "[BLD]"
                
            print(f"{marker:<3} {c.name:<15} {c.initiative:<5} {hp_str:<12} {ac_str:<4} {c_type:<8} {hp_visual} {conds}")
        print("-" * 75)

def select_database():
    db_files = [f for f in os.listdir('.') if f.endswith('.db')]
    if not db_files:
        return "./combat.db"
    if len(db_files) == 1:
        return db_files[0]
    
    print("Multiple combat instances found:")
    for i, db in enumerate(db_files, 1):
        print(f"{i}. {db}")
    
    while True:
        try:
            choice = int(input(f"Select an instance (1-{len(db_files)}): "))
            if 1 <= choice <= len(db_files):
                return db_files[choice - 1]
            else:
                print(f"Please enter a number between 1 and {len(db_files)}.")
        except ValueError:
            print("Invalid input. Please enter a number.")

def main():
    db_path = select_database()
    tracker = InitiativeTracker(db_path)

    
    while True:
        clear_screen()
        tracker.display()
        print(f"CMDSpell - Connected to {db_path}")
        cmd_input = input("\nCommands: add, next, dam, heal, rem, cond, history, quit\n> ").strip().split()
        
        if not cmd_input:
            continue
            
        cmd = cmd_input[0].lower()
        
        try:
            if cmd == "add":
                name = input("Name: ")
                init = int(input("Initiative: "))
                is_p = input("Is Player? (y/n): ").lower() == 'y'
                
                hp = None
                ac = None
                if not is_p:
                    hp = int(input("Max HP: "))
                    ac = int(input("AC: "))
                else:
                    skip = input("Skip HP/AC? (y/n): ").lower() == 'y'
                    if not skip:
                        hp = int(input("Max HP: "))
                        ac = int(input("AC: "))
                
                tracker.add_combatant(name, init, hp, ac, is_p)
            
            elif cmd == "next":
                tracker.next_turn()
            
            elif cmd == "dam":
                name = input("Target Name: ")
                amount = int(input("Damage Amount: "))
                d_type = input("Damage Type: ")
                if not tracker.take_damage(name, amount, d_type):
                    print("Combatant not found.")
                    input("\nPress Enter to continue...")
            
            elif cmd == "heal":
                name = input("Target Name: ")
                amount = int(input("Heal Amount: "))
                if not tracker.heal(name, amount):
                    print("Combatant not found.")
                    input("\nPress Enter to continue...")
            
            elif cmd == "rem":
                name = input("Name to remove: ")
                tracker.remove_combatant(name)
            
            elif cmd == "cond":
                sub = input("Subcommand (add/rem): ").lower()
                name = input("Target Name: ")
                cond = input("Condition: ")
                if sub == "add":
                    tracker.add_condition(name, cond)
                elif sub == "rem":
                    tracker.remove_condition(name, cond)
            
            elif cmd == "history":
                name = input("Target Name: ")
                found = False
                for c in tracker.combatants:
                    if c.name.lower() == name.lower():
                        found = True
                        print(f"\n--- History for {c.name} ---")
                        if not c.damage_history:
                            print("No history recorded.")
                        for entry in c.damage_history:
                            if entry["type"] == "damage":
                                print(f"- Took {entry['amount']} {entry['damage_type']} damage")
                            else:
                                print(f"- Healed {entry['amount']} HP")
                        input("\nPress Enter to continue...")
                        break
                if not found:
                    print("Combatant not found.")
                    input("\nPress Enter to continue...")
            
            elif cmd == "quit":
                break
            else:
                print("Unknown command.")
                input("\nPress Enter to continue...")
        except ValueError:
            print("Invalid input.")
            input("\nPress Enter to continue...")
        except Exception as e:
            print(f"An error occurred: {e}")
            input("\nPress Enter to continue...")

if __name__ == "__main__":
    main()
