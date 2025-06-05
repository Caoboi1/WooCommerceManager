"""
AI Configuration Dialog - Dialog cấu hình Google Gemini API và prompts
"""

import json
import os
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QTextEdit, QPushButton, QLabel, QGroupBox,
    QMessageBox, QProgressBar, QTabWidget, QWidget
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont

from .gemini_service import GeminiService

class APITestThread(QThread):
    """Thread để test API key"""
    result_ready = pyqtSignal(bool, str)
    
    def __init__(self, api_key: str):
        super().__init__()
        self.api_key = api_key
    
    def run(self):
        service = GeminiService(self.api_key)
        success, message = service.test_api_key()
        self.result_ready.emit(success, message)

class AIConfigDialog(QDialog):
    """Dialog cấu hình AI"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.config_file = "ai_config.json"
        self.test_thread = None
        self.init_ui()
        self.load_config()
    
    def init_ui(self):
        """Khởi tạo giao diện"""
        self.setWindowTitle("Cấu hình AI - Google Gemini")
        self.setModal(True)
        self.resize(600, 500)
        
        layout = QVBoxLayout(self)
        
        # Tab widget
        tab_widget = QTabWidget()
        
        # Tab 1: API Configuration
        api_tab = QWidget()
        api_layout = QVBoxLayout(api_tab)
        
        # API Keys section
        api_group = QGroupBox("Google Gemini API Keys")
        api_group_layout = QVBoxLayout(api_group)
        
        # Multiple API Keys
        keys_layout = QVBoxLayout()
        
        self.api_keys = []  # List of QLineEdit widgets
        self.api_keys_layout = QVBoxLayout()
        
        # Add first API key
        self.add_api_key_field()
        
        keys_layout.addLayout(self.api_keys_layout)
        
        # Buttons for managing API keys
        keys_buttons = QHBoxLayout()
        
        self.add_key_btn = QPushButton("➕ Thêm API Key")
        self.add_key_btn.clicked.connect(self.add_api_key_field)
        keys_buttons.addWidget(self.add_key_btn)
        
        self.remove_key_btn = QPushButton("➖ Xóa API Key")
        self.remove_key_btn.clicked.connect(self.remove_api_key_field)
        keys_buttons.addWidget(self.remove_key_btn)
        
        keys_buttons.addStretch()
        
        keys_layout.addLayout(keys_buttons)
        api_group_layout.addLayout(keys_layout)
        
        # Test API button
        test_layout = QHBoxLayout()
        self.test_api_btn = QPushButton("🧪 Test All API Keys")
        self.test_api_btn.clicked.connect(self.test_all_api_keys)
        test_layout.addWidget(self.test_api_btn)
        
        self.test_progress = QProgressBar()
        self.test_progress.setVisible(False)
        test_layout.addWidget(self.test_progress)
        
        self.test_result_label = QLabel("")
        test_layout.addWidget(self.test_result_label)
        test_layout.addStretch()
        
        api_group_layout.addLayout(test_layout)
        api_layout.addWidget(api_group)
        
        # Instructions
        instructions_group = QGroupBox("Hướng dẫn lấy API Key")
        instructions_layout = QVBoxLayout(instructions_group)
        
        instructions_text = QLabel(
            "1. Truy cập: https://aistudio.google.com/app/apikey\n"
            "2. Đăng nhập tài khoản Google\n"
            "3. Click 'Create API Key'\n"
            "4. Copy API key và dán vào ô trên\n"
            "5. Click 'Test API Key' để kiểm tra"
        )
        instructions_text.setStyleSheet("color: #666; padding: 10px;")
        instructions_layout.addWidget(instructions_text)
        
        api_layout.addWidget(instructions_group)
        api_layout.addStretch()
        
        tab_widget.addTab(api_tab, "🔑 API Key")
        
        # Tab 2: Prompts
        prompts_tab = QWidget()
        prompts_layout = QVBoxLayout(prompts_tab)
        
        # Title prompt
        title_group = QGroupBox("Prompt tạo tiêu đề")
        title_layout = QVBoxLayout(title_group)
        
        self.title_prompt_edit = QTextEdit()
        self.title_prompt_edit.setMaximumHeight(100)
        self.title_prompt_edit.setPlainText(
            "Analyze this product image and create a compelling English product title based on the original folder name '{folder_name}'. "
            "Requirements:\n"
            "- Write ONLY in English language for US market\n"
            "- Length: exactly 50-60 characters (optimal for SEO display) - count carefully\n"
            "- Maximum 65 characters if needed but prioritize 50-60 range\n"
            "- Use the original title '{folder_name}' as reference but improve it\n"
            "- Place most important keywords at the BEGINNING of title\n"
            "- Include clear product name and team/brand name prominently\n"
            "- Add key product attributes (size, color, material) if visible in image\n"
            "- Create UNIQUE title that stands out from competitors (avoid generic phrases)\n"
            "- Analyze Google search trends and popular keywords for this product category\n"
            "- Use marketing language that attracts US sports fans and drives search traffic\n"
            "- Make it SEO-optimized with high-search-volume keywords for American audience\n"
            "- Focus on emotional appeal and fan pride with unique selling points\n"
            "- Use American English terminology (game day, playoffs, championship)\n"
            "- Ensure title is distinctive and not duplicated in the market\n"
            "- Target specific search intent and user needs\n"
            "- Write naturally for users, avoid keyword stuffing\n"
            "- Each title must be completely unique for this specific product\n"
            "- Return ONLY the improved title, no explanations or quotes"
        )
        title_layout.addWidget(self.title_prompt_edit)
        
        prompts_layout.addWidget(title_group)
        
        # Description prompt
        description_group = QGroupBox("Prompt tạo mô tả")
        description_layout = QVBoxLayout(description_group)
        
        self.description_prompt_edit = QTextEdit()
        self.description_prompt_edit.setMaximumHeight(120)
        self.description_prompt_edit.setPlainText(
            "Analyze this product image and write a detailed English product description based on '{folder_name}' for the US sports market. "
            "Requirements:\n"
            "- Write ONLY in English language for American customers\n"
            "- Length: exactly 300-500 characters (count carefully)\n"
            "- Reference the original product name '{folder_name}' but enhance it\n"
            "- Create UNIQUE description that differentiates from competitors\n"
            "- Place primary keywords naturally at the beginning of description\n"
            "- Include specific product details: team name, product type, size/material if visible\n"
            "- Research and incorporate trending keywords from Google search data\n"
            "- Use storytelling style that evokes emotions and fan pride\n"
            "- Describe specific visual details from image: colors, materials, design, team logos\n"
            "- Highlight key benefits for US fans: comfort, style, showing team support\n"
            "- Add 2-3 bullet points for key features visible in the image\n"
            "- Include emotional phrases about team loyalty and fan experience\n"
            "- Use American sports terminology: 'game day', 'tailgate', 'playoffs', 'championship'\n"
            "- Target specific search intent with high-converting keywords\n"
            "- End with a strong call-to-action in American English\n"
            "- Make it distinctive and avoid duplicated content in the market\n"
            "- Focus on what makes US fans feel proud wearing/using this item\n"
            "- Write naturally for users while being SEO-optimized\n"
            "- Avoid keyword stuffing - prioritize readability and user experience\n"
            "- Each description must be completely unique for this specific product\n"
            "- Return ONLY the description, no explanations"
        )
        description_layout.addWidget(self.description_prompt_edit)
        
        prompts_layout.addWidget(description_group)
        
        # Variables help
        variables_group = QGroupBox("Variables có thể sử dụng")
        variables_layout = QVBoxLayout(variables_group)
        
        variables_text = QLabel(
            "• {folder_name} - Tên thư mục gốc\n"
            "• Ảnh đầu tiên trong thư mục sẽ được gửi kèm prompt"
        )
        variables_text.setStyleSheet("color: #666; padding: 5px;")
        variables_layout.addWidget(variables_text)
        
        prompts_layout.addWidget(variables_group)
        prompts_layout.addStretch()
        
        tab_widget.addTab(prompts_tab, "📝 Prompts")
        
        layout.addWidget(tab_widget)
        
        # Buttons
        buttons_layout = QHBoxLayout()
        
        self.save_btn = QPushButton("💾 Lưu cấu hình")
        self.save_btn.clicked.connect(self.save_config)
        buttons_layout.addWidget(self.save_btn)
        
        self.reset_btn = QPushButton("🔄 Reset")
        self.reset_btn.clicked.connect(self.reset_config)
        buttons_layout.addWidget(self.reset_btn)
        
        buttons_layout.addStretch()
        
        self.cancel_btn = QPushButton("❌ Hủy")
        self.cancel_btn.clicked.connect(self.reject)
        buttons_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(buttons_layout)
    
    def add_api_key_field(self):
        """Thêm field API key mới"""
        key_layout = QHBoxLayout()
        
        # API Key input
        api_key_edit = QLineEdit()
        api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        api_key_edit.setPlaceholderText(f"API Key #{len(self.api_keys) + 1}...")
        key_layout.addWidget(QLabel(f"Key {len(self.api_keys) + 1}:"))
        key_layout.addWidget(api_key_edit)
        
        # Show/Hide button
        show_btn = QPushButton("👁️")
        show_btn.setMaximumWidth(30)
        show_btn.clicked.connect(lambda: self.toggle_api_key_visibility(api_key_edit, show_btn))
        key_layout.addWidget(show_btn)
        
        # Test single key button
        test_btn = QPushButton("🧪")
        test_btn.setMaximumWidth(30)
        test_btn.setToolTip("Test API key này")
        test_btn.clicked.connect(lambda: self.test_single_api_key(api_key_edit))
        key_layout.addWidget(test_btn)
        
        self.api_keys_layout.addLayout(key_layout)
        self.api_keys.append(api_key_edit)
        
        # Update remove button state
        if hasattr(self, 'remove_key_btn'):
            self.remove_key_btn.setEnabled(len(self.api_keys) > 1)
    
    def remove_api_key_field(self):
        """Xóa field API key cuối cùng"""
        if len(self.api_keys) > 1:
            # Remove last layout
            last_layout = self.api_keys_layout.takeAt(self.api_keys_layout.count() - 1)
            if last_layout:
                while last_layout.count():
                    child = last_layout.takeAt(0)
                    if child.widget():
                        child.widget().deleteLater()
                last_layout.deleteLater()
            
            # Remove from list
            if self.api_keys:
                self.api_keys.pop()
            
            # Update remove button state
            if hasattr(self, 'remove_key_btn'):
                self.remove_key_btn.setEnabled(len(self.api_keys) > 1)
    
    def toggle_api_key_visibility(self, edit_widget, button):
        """Toggle hiển thị/ẩn API key"""
        if edit_widget.echoMode() == QLineEdit.EchoMode.Password:
            edit_widget.setEchoMode(QLineEdit.EchoMode.Normal)
            button.setText("🙈")
        else:
            edit_widget.setEchoMode(QLineEdit.EchoMode.Password)
            button.setText("👁️")
    
    def test_single_api_key(self, api_key_edit):
        """Test một API key cụ thể"""
        api_key = api_key_edit.text().strip()
        if not api_key:
            QMessageBox.warning(self, "Cảnh báo", "Vui lòng nhập API key!")
            return
        
        # Test API key
        self.test_thread = APITestThread(api_key)
        self.test_thread.result_ready.connect(lambda success, message: self.on_single_test_result(success, message, api_key_edit))
        self.test_thread.start()
    
    def test_all_api_keys(self):
        """Test tất cả API keys"""
        api_keys = [edit.text().strip() for edit in self.api_keys if edit.text().strip()]
        
        if not api_keys:
            QMessageBox.warning(self, "Cảnh báo", "Vui lòng nhập ít nhất một API key!")
            return
        
        # Disable button và hiển thị progress
        self.test_api_btn.setEnabled(False)
        self.test_progress.setVisible(True)
        self.test_progress.setRange(0, len(api_keys))
        self.test_progress.setValue(0)
        self.test_result_label.setText("Đang test...")
        
        # Test từng key
        self.test_results = []
        self.current_test_index = 0
        self.all_api_keys = api_keys
        self.test_next_key()
    
    def test_next_key(self):
        """Test API key tiếp theo"""
        if self.current_test_index < len(self.all_api_keys):
            api_key = self.all_api_keys[self.current_test_index]
            self.test_thread = APITestThread(api_key)
            self.test_thread.result_ready.connect(self.on_batch_test_result)
            self.test_thread.start()
        else:
            # Hoàn thành test tất cả
            self.on_all_tests_completed()
    
    def on_single_test_result(self, success: bool, message: str, api_key_edit):
        """Xử lý kết quả test một API key"""
        if success:
            api_key_edit.setStyleSheet("border: 2px solid green;")
            QMessageBox.information(self, "Thành công", f"API key hợp lệ: {message}")
        else:
            api_key_edit.setStyleSheet("border: 2px solid red;")
            QMessageBox.warning(self, "Lỗi", f"API key không hợp lệ: {message}")
        
        if self.test_thread:
            self.test_thread.deleteLater()
            self.test_thread = None
    
    def on_batch_test_result(self, success: bool, message: str):
        """Xử lý kết quả test batch"""
        self.test_results.append({
            'index': self.current_test_index,
            'success': success,
            'message': message,
            'api_key': self.all_api_keys[self.current_test_index][:10] + "..."
        })
        
        self.current_test_index += 1
        self.test_progress.setValue(self.current_test_index)
        self.test_result_label.setText(f"Đã test {self.current_test_index}/{len(self.all_api_keys)} keys...")
        
        if self.test_thread:
            self.test_thread.deleteLater()
            self.test_thread = None
        
        # Test key tiếp theo
        self.test_next_key()
    
    def on_all_tests_completed(self):
        """Hoàn thành test tất cả API keys"""
        self.test_api_btn.setEnabled(True)
        self.test_progress.setVisible(False)
        
        # Tổng hợp kết quả
        valid_count = sum(1 for result in self.test_results if result['success'])
        total_count = len(self.test_results)
        
        if valid_count > 0:
            self.test_result_label.setText(f"✅ {valid_count}/{total_count} keys hợp lệ")
            self.test_result_label.setStyleSheet("color: green;")
            
            # Hiển thị chi tiết
            details = []
            for i, result in enumerate(self.test_results):
                status = "✅" if result['success'] else "❌"
                details.append(f"Key {i+1}: {status} {result['message']}")
            
            QMessageBox.information(self, "Kết quả test", "\n".join(details))
        else:
            self.test_result_label.setText(f"❌ {valid_count}/{total_count} keys hợp lệ")
            self.test_result_label.setStyleSheet("color: red;")
            QMessageBox.warning(self, "Thất bại", "Không có API key nào hợp lệ!")
    
    def load_config(self):
        """Load cấu hình từ file"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                # Load API keys
                api_keys = config.get('api_keys', [])
                if not api_keys and config.get('api_key'):  # Backward compatibility
                    api_keys = [config['api_key']]
                
                # Clear existing keys and add loaded ones
                self.api_keys.clear()
                # Clear layout
                while self.api_keys_layout.count():
                    child = self.api_keys_layout.takeAt(0)
                    if child.layout():
                        while child.layout().count():
                            grandchild = child.layout().takeAt(0)
                            if grandchild.widget():
                                grandchild.widget().deleteLater()
                        child.layout().deleteLater()
                
                # Add API keys
                if api_keys:
                    for api_key in api_keys:
                        self.add_api_key_field()
                        if self.api_keys:
                            self.api_keys[-1].setText(api_key)
                else:
                    # Ensure at least one field
                    self.add_api_key_field()
                
                # Load prompts
                if 'title_prompt' in config:
                    self.title_prompt_edit.setPlainText(config['title_prompt'])
                
                if 'description_prompt' in config:
                    self.description_prompt_edit.setPlainText(config['description_prompt'])
                    
        except Exception as e:
            QMessageBox.warning(self, "Cảnh báo", f"Không thể load cấu hình: {str(e)}")
    
    def save_config(self):
        """Lưu cấu hình"""
        try:
            api_keys = [edit.text().strip() for edit in self.api_keys if edit.text().strip()]
            
            if not api_keys:
                QMessageBox.warning(self, "Cảnh báo", "Vui lòng nhập ít nhất một API key!")
                return
            
            config = {
                'api_keys': api_keys,
                'api_key': api_keys[0],  # Backward compatibility
                'title_prompt': self.title_prompt_edit.toPlainText().strip(),
                'description_prompt': self.description_prompt_edit.toPlainText().strip()
            }
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            
            QMessageBox.information(self, "Thành công", f"Đã lưu cấu hình AI với {len(api_keys)} API keys!")
            self.accept()
            
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể lưu cấu hình: {str(e)}")
    
    def reset_config(self):
        """Reset cấu hình về mặc định"""
        reply = QMessageBox.question(
            self, "Xác nhận", 
            "Bạn có chắc muốn reset cấu hình về mặc định?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # Clear all API keys and add one empty field
            self.api_keys.clear()
            while self.api_keys_layout.count():
                child = self.api_keys_layout.takeAt(0)
                if child.layout():
                    while child.layout().count():
                        grandchild = child.layout().takeAt(0)
                        if grandchild.widget():
                            grandchild.widget().deleteLater()
                    child.layout().deleteLater()
            
            self.add_api_key_field()
            
            # Reset prompts
            self.title_prompt_edit.setPlainText(
                "Analyze this product image and create a compelling English product title based on the original folder name '{folder_name}'. "
                "Requirements:\n"
                "- Write ONLY in English language for US market\n"
                "- Length: exactly 50-60 characters (optimal for SEO display) - count carefully\n"
                "- Maximum 65 characters if needed but prioritize 50-60 range\n"
                "- Use the original title '{folder_name}' as reference but improve it\n"
                "- Place most important keywords at the BEGINNING of title\n"
                "- Include clear product name and team/brand name prominently\n"
                "- Add key product attributes (size, color, material) if visible in image\n"
                "- Create UNIQUE title that stands out from competitors (avoid generic phrases)\n"
                "- Analyze Google search trends and popular keywords for this product category\n"
                "- Use marketing language that attracts US sports fans and drives search traffic\n"
                "- Make it SEO-optimized with high-search-volume keywords for American audience\n"
                "- Focus on emotional appeal and fan pride with unique selling points\n"
                "- Use American English terminology (game day, playoffs, championship)\n"
                "- Ensure title is distinctive and not duplicated in the market\n"
                "- Target specific search intent and user needs\n"
                "- Write naturally for users, avoid keyword stuffing\n"
                "- Each title must be completely unique for this specific product\n"
                "- Return ONLY the improved title, no explanations or quotes"
            )
            
            self.description_prompt_edit.setPlainText(
                "Analyze this product image and write a detailed English product description based on '{folder_name}' for the US sports market. "
                "Requirements:\n"
                "- Write ONLY in English language for American customers\n"
                "- Length: exactly 300-500 characters (count carefully)\n"
                "- Reference the original product name '{folder_name}' but enhance it\n"
                "- Create UNIQUE description that differentiates from competitors\n"
                "- Place primary keywords naturally at the beginning of description\n"
                "- Include specific product details: team name, product type, size/material if visible\n"
                "- Research and incorporate trending keywords from Google search data\n"
                "- Use storytelling style that evokes emotions and fan pride\n"
                "- Describe specific visual details from image: colors, materials, design, team logos\n"
                "- Highlight key benefits for US fans: comfort, style, showing team support\n"
                "- Add 2-3 bullet points for key features visible in the image\n"
                "- Include emotional phrases about team loyalty and fan experience\n"
                "- Use American sports terminology: 'game day', 'tailgate', 'playoffs', 'championship'\n"
                "- Target specific search intent with high-converting keywords\n"
                "- End with a strong call-to-action in American English\n"
                "- Make it distinctive and avoid duplicated content in the market\n"
                "- Focus on what makes US fans feel proud wearing/using this item\n"
                "- Write naturally for users while being SEO-optimized\n"
                "- Avoid keyword stuffing - prioritize readability and user experience\n"
                "- Each description must be completely unique for this specific product\n"
                "- Return ONLY the description, no explanations"
            )
    
    def get_config(self) -> dict:
        """Lấy cấu hình hiện tại"""
        api_keys = [edit.text().strip() for edit in self.api_keys if edit.text().strip()]
        return {
            'api_keys': api_keys,
            'api_key': api_keys[0] if api_keys else '',  # Backward compatibility
            'title_prompt': self.title_prompt_edit.toPlainText().strip(),
            'description_prompt': self.description_prompt_edit.toPlainText().strip()
        }