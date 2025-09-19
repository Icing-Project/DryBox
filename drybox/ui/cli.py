# CLI interface for DryBox
import sys
import yaml
import argparse
from pathlib import Path
from typing import Optional, Dict, Any

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from drybox.core.runner import Runner


class CLIInterface:
    """Command-line interface for DryBox"""

    def __init__(self):
        self.current_scenario: Optional[Dict[str, Any]] = None
        self.scenario_path: Optional[str] = None

    def run(self):
        """Run the CLI interface"""
        parser = argparse.ArgumentParser(description="DryBox CLI")
        parser.add_argument('scenario', nargs='?', help='Scenario file to load')
        parser.add_argument('--run', action='store_true', help='Run scenario immediately')
        parser.add_argument('--list', action='store_true', help='List available scenarios')
        args = parser.parse_args()

        if args.list:
            self.list_scenarios()
        elif args.scenario:
            self.load_scenario(args.scenario)
            if args.run:
                self.run_scenario()
            else:
                self.interactive_mode()
        else:
            self.interactive_mode()

    def list_scenarios(self):
        """List available scenarios"""
        scenarios_dir = Path("drybox/scenarios")
        if not scenarios_dir.exists():
            print("No scenarios directory found")
            return

        print("\nAvailable scenarios:")
        print("-" * 50)

        for yaml_file in scenarios_dir.glob("*.yaml"):
            try:
                with open(yaml_file, 'r') as f:
                    data = yaml.safe_load(f)
                    title = data.get('title', 'Untitled')
                    duration = data.get('duration_ms', 0)
                    print(f"{yaml_file.name:30} {title} ({duration}ms)")
            except:
                print(f"{yaml_file.name:30} [Error reading file]")

    def load_scenario(self, path: str):
        """Load a scenario file"""
        try:
            with open(path, 'r') as f:
                self.current_scenario = yaml.safe_load(f)
                self.scenario_path = path

            print(f"\nLoaded scenario: {Path(path).name}")
            self.show_scenario_info()

        except Exception as e:
            print(f"Error loading scenario: {e}")

    def show_scenario_info(self):
        """Display current scenario information"""
        if not self.current_scenario:
            print("No scenario loaded")
            return

        print(f"\nTitle: {self.current_scenario.get('title', 'Untitled')}")
        print(f"Duration: {self.current_scenario.get('duration_ms', 0)} ms")

        if 'adapters' in self.current_scenario:
            print("\nAdapters:")
            for side, adapter in self.current_scenario['adapters'].items():
                print(f"  {side}: {adapter.get('type', 'unknown')}")

        if 'net' in self.current_scenario:
            print(f"\nNetwork: {self.current_scenario['net'].get('type', 'unknown')}")

        if 'radio' in self.current_scenario:
            print("\nRadio:")
            radio = self.current_scenario['radio']
            if 'vocoder' in radio:
                print(f"  Vocoder: {radio['vocoder'].get('type', 'unknown')}")
            if 'channel' in radio:
                print(f"  Channel: {radio['channel'].get('type', 'unknown')}")

    def run_scenario(self):
        """Run the current scenario"""
        if not self.current_scenario:
            print("No scenario loaded")
            return

        print(f"\nRunning scenario: {self.current_scenario.get('title', 'Untitled')}")
        print("-" * 50)

        try:
            # Create runner
            runner = Runner()

            # Run with event capture
            events = []
            runner.run_scenario(self.current_scenario, events=events)

            # Display events
            print("\nEvents:")
            for event in events:
                t_ms = event['t_ms']
                side = event['side']
                typ = event['typ']
                payload = event.get('payload', {})
                print(f"{t_ms:6d}ms [{side}] {typ}: {payload}")

            print(f"\nScenario completed. {len(events)} events captured.")

        except Exception as e:
            print(f"Error running scenario: {e}")

    def interactive_mode(self):
        """Interactive command mode"""
        print("\nDryBox CLI - Interactive Mode")
        print("Commands: load <file>, run, info, list, quit")
        print("-" * 50)

        while True:
            try:
                cmd = input("\n> ").strip().lower()

                if cmd == "quit" or cmd == "exit":
                    break
                elif cmd == "list":
                    self.list_scenarios()
                elif cmd.startswith("load "):
                    file_path = cmd[5:].strip()
                    self.load_scenario(file_path)
                elif cmd == "run":
                    self.run_scenario()
                elif cmd == "info":
                    self.show_scenario_info()
                elif cmd == "help":
                    print("Commands:")
                    print("  load <file> - Load a scenario file")
                    print("  run        - Run the current scenario")
                    print("  info       - Show current scenario info")
                    print("  list       - List available scenarios")
                    print("  quit       - Exit the program")
                else:
                    print(f"Unknown command: {cmd}")

            except KeyboardInterrupt:
                print("\nUse 'quit' to exit")
            except EOFError:
                break


def main():
    """Main entry point"""
    cli = CLIInterface()
    cli.run()


if __name__ == "__main__":
    main()
