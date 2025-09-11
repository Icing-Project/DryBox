# Widget for displaying scenario details
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QSplitter
from PyQt6.QtWidgets import QTreeWidget, QTreeWidgetItem, QTextEdit
from PyQt6.QtCore import Qt
from typing import Dict, Any, List


class ScenarioWidget(QWidget):
    """Widget for displaying scenario structure"""
    
    def __init__(self):
        super().__init__()
        self.init_ui()
        
    def init_ui(self):
        """Initialize UI components"""
        layout = QVBoxLayout(self)
        
        # Splitter for tree and details
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)
        
        # Tree view for scenario structure
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Component", "Type", "Value"])
        self.tree.itemSelectionChanged.connect(self.on_selection_changed)
        splitter.addWidget(self.tree)
        
        # Details view
        self.details = QTextEdit()
        self.details.setReadOnly(True)
        splitter.addWidget(self.details)
        
        # Set splitter sizes
        splitter.setSizes([400, 600])
        
    def load_scenario(self, scenario_data: Dict[str, Any]):
        """Load scenario data into tree"""
        self.tree.clear()
        
        # Add metadata
        meta_item = QTreeWidgetItem(self.tree)
        meta_item.setText(0, "Metadata")
        meta_item.setText(1, "section")
        
        if 'title' in scenario_data:
            title_item = QTreeWidgetItem(meta_item)
            title_item.setText(0, "Title")
            title_item.setText(2, scenario_data['title'])
            
        if 'duration_ms' in scenario_data:
            duration_item = QTreeWidgetItem(meta_item)
            duration_item.setText(0, "Duration")
            duration_item.setText(2, f"{scenario_data['duration_ms']} ms")
            
        # Add adapters
        adapters_item = QTreeWidgetItem(self.tree)
        adapters_item.setText(0, "Adapters")
        adapters_item.setText(1, "section")
        
        if 'adapters' in scenario_data:
            for side, adapter_cfg in scenario_data['adapters'].items():
                adapter_item = QTreeWidgetItem(adapters_item)
                adapter_item.setText(0, f"Side {side}")
                adapter_item.setText(1, "adapter")
                adapter_item.setText(2, adapter_cfg.get('type', 'unknown'))
                adapter_item.setData(0, Qt.ItemDataRole.UserRole, adapter_cfg)
                
        # Add network configuration
        if 'net' in scenario_data:
            net_item = QTreeWidgetItem(self.tree)
            net_item.setText(0, "Network")
            net_item.setText(1, "section")
            
            net_cfg = scenario_data['net']
            self._add_dict_to_tree(net_cfg, net_item)
            
        # Add radio configuration
        if 'radio' in scenario_data:
            radio_item = QTreeWidgetItem(self.tree)
            radio_item.setText(0, "Radio")
            radio_item.setText(1, "section")
            
            radio_cfg = scenario_data['radio']
            self._add_dict_to_tree(radio_cfg, radio_item)
            
        # Expand all
        self.tree.expandAll()
        
    def _add_dict_to_tree(self, data: Dict[str, Any], parent: QTreeWidgetItem):
        """Add dictionary to tree recursively"""
        for key, value in data.items():
            item = QTreeWidgetItem(parent)
            item.setText(0, key)
            
            if isinstance(value, dict):
                item.setText(1, "dict")
                self._add_dict_to_tree(value, item)
            elif isinstance(value, list):
                item.setText(1, "list")
                item.setText(2, f"[{len(value)} items]")
                for i, val in enumerate(value):
                    list_item = QTreeWidgetItem(item)
                    list_item.setText(0, f"[{i}]")
                    if isinstance(val, dict):
                        self._add_dict_to_tree(val, list_item)
                    else:
                        list_item.setText(2, str(val))
            else:
                item.setText(1, type(value).__name__)
                item.setText(2, str(value))
                
    def on_selection_changed(self):
        """Handle tree selection changes"""
        items = self.tree.selectedItems()
        if items:
            item = items[0]
            # Get stored data
            data = item.data(0, Qt.ItemDataRole.UserRole)
            if data:
                # Show formatted JSON/YAML
                import json
                self.details.setText(json.dumps(data, indent=2))
            else:
                # Show item info
                info = f"Component: {item.text(0)}\n"
                info += f"Type: {item.text(1)}\n"
                if item.text(2):
                    info += f"Value: {item.text(2)}\n"
                self.details.setText(info)