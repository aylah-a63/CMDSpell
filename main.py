import sys
import os
from openArcana import *

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

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
        cmd_input = input("\nCommands: add, next, dam, heal, rem, clear, cond, history, quit\n> ").strip().split()
        
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

            elif cmd == "clear":
                if input("Are you sure you want to delete all combatants? (y/n): ").lower() == 'y':
                    tracker.clear_combatants()
            
            elif cmd == "cond":
                sub = input("Subcommand (add/rem): ").lower()
                name = input("Target Name: ")
                cond = input("Condition: ")
                if sub == "add":
                    print("Duration cheat sheet: 1 round = 6 seconds. 10 rounds = 1 minute.")
                    duration_input = input("Duration in rounds (optional, press Enter to skip): ")
                    duration = int(duration_input) if duration_input.strip() else None
                    tracker.add_condition(name, cond, duration)
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
