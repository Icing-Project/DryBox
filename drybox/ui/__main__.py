# Main entry point for UI module
import sys
import argparse
from pathlib import Path


def main():
    """Main entry point for DryBox UI"""
    parser = argparse.ArgumentParser(description="DryBox UI")
    parser.add_argument('--qt', action='store_true', help='Use Qt GUI (requires PyQt6)')
    parser.add_argument('--web', action='store_true', help='Use web interface')
    args = parser.parse_args()
    
    if args.qt:
        try:
            from PyQt6.QtWidgets import QApplication
            # Import the beautiful GUI
            sys.path.insert(0, str(Path(__file__).parent.parent.parent))
            from drybox_correct_gui import CorrectDryBoxGUI
            
            app = QApplication(sys.argv)
            app.setStyle("Fusion")
            window = CorrectDryBoxGUI()
            window.show()
            sys.exit(app.exec())
            
        except ImportError as e:
            print(f"Error: Qt GUI requires PyQt6 to be installed")
            print(f"Install with: pip install PyQt6")
            print(f"Error details: {e}")
            sys.exit(1)
            
    elif args.web:
        print("Web interface not yet implemented")
        sys.exit(1)
        
    else:
        print("DryBox UI - Please specify an interface type")
        print("Usage:")
        print("  python -m drybox.ui --qt    # Qt GUI (requires PyQt6)")
        print("  python -m drybox.ui --web   # Web interface (not yet implemented)")
        sys.exit(0)


if __name__ == "__main__":
    main()