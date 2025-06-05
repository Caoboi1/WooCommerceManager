
"""
Google Gemini AI Service - Tích hợp Google Gemini API để đọc ảnh và tạo nội dung
"""

import os
import logging
import base64
import requests
from typing import Dict, Any, Optional, List
from PyQt6.QtCore import QObject, pyqtSignal

class GeminiService(QObject):
    """Service để tương tác với Google Gemini API với hỗ trợ nhiều API keys"""
    
    # Signals
    content_generated = pyqtSignal(str, dict)  # folder_path, result
    error_occurred = pyqtSignal(str, str)  # folder_path, error_message
    
    def __init__(self, api_key: str = "", api_keys: List[str] = None):
        super().__init__()
        self.api_keys = api_keys or ([api_key] if api_key else [])
        self.current_key_index = 0
        self.failed_keys = set()  # Track failed keys
        self.logger = logging.getLogger(__name__)
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
        
        # For backward compatibility
        self.api_key = self.get_current_api_key()
        
    def set_api_key(self, api_key: str):
        """Đặt API key (backward compatibility)"""
        self.api_keys = [api_key] if api_key else []
        self.current_key_index = 0
        self.failed_keys.clear()
        self.api_key = api_key
    
    def set_api_keys(self, api_keys: List[str]):
        """Đặt nhiều API keys"""
        self.api_keys = [key.strip() for key in api_keys if key.strip()]
        self.current_key_index = 0
        self.failed_keys.clear()
        self.api_key = self.get_current_api_key()
    
    def get_current_api_key(self) -> str:
        """Lấy API key hiện tại"""
        if not self.api_keys:
            return ""
        
        # Tìm key hợp lệ tiếp theo
        start_index = self.current_key_index
        for _ in range(len(self.api_keys)):
            key = self.api_keys[self.current_key_index]
            if self.current_key_index not in self.failed_keys:
                return key
            self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
            if self.current_key_index == start_index:
                break
        
        # Nếu tất cả keys đều failed, reset và thử lại
        if len(self.failed_keys) == len(self.api_keys):
            self.failed_keys.clear()
            self.current_key_index = 0
        
        return self.api_keys[self.current_key_index] if self.api_keys else ""
    
    def rotate_api_key(self):
        """Chuyển sang API key tiếp theo"""
        if len(self.api_keys) <= 1:
            return
        
        # Mark current key as failed
        self.failed_keys.add(self.current_key_index)
        
        # Move to next key
        self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
        self.api_key = self.get_current_api_key()
        
        self.logger.info(f"Rotated to API key #{self.current_key_index + 1}")
    
    def has_available_keys(self) -> bool:
        """Kiểm tra còn API key khả dụng không"""
        return len(self.failed_keys) < len(self.api_keys)
    
    def get_api_keys_status(self) -> Dict[str, Any]:
        """Lấy trạng thái của tất cả API keys"""
        return {
            'total_keys': len(self.api_keys),
            'current_index': self.current_key_index,
            'failed_count': len(self.failed_keys),
            'available_count': len(self.api_keys) - len(self.failed_keys),
            'current_key_preview': self.get_current_api_key()[:10] + "..." if self.get_current_api_key() else ""
        }
        
    def test_api_key(self) -> tuple[bool, str]:
        """Test API key có hợp lệ không"""
        if not self.api_key:
            return False, "API key không được để trống"
            
        try:
            # Test với một request đơn giản
            url = f"{self.base_url}?key={self.api_key}"
            
            data = {
                "contents": [{
                    "parts": [{"text": "Hello, test connection"}]
                }]
            }
            
            response = requests.post(url, json=data, timeout=10)
            
            if response.status_code == 200:
                return True, "API key hợp lệ"
            elif response.status_code == 400:
                result = response.json()
                if "API_KEY_INVALID" in str(result):
                    return False, "API key không hợp lệ"
                return True, "API key hợp lệ"
            else:
                return False, f"Lỗi API: {response.status_code}"
                
        except Exception as e:
            return False, f"Lỗi kết nối: {str(e)}"
    
    def encode_image_to_base64(self, image_path: str) -> Optional[str]:
        """Encode ảnh thành base64"""
        try:
            with open(image_path, "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
                return encoded_string
        except Exception as e:
            self.logger.error(f"Lỗi encode ảnh {image_path}: {str(e)}")
            return None
    
    def get_image_mime_type(self, image_path: str) -> str:
        """Lấy MIME type của ảnh"""
        ext = os.path.splitext(image_path)[1].lower()
        mime_types = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg', 
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.bmp': 'image/bmp',
            '.webp': 'image/webp'
        }
        return mime_types.get(ext, 'image/jpeg')
    
    def find_first_image(self, folder_path: str) -> Optional[str]:
        """Tìm ảnh đầu tiên trong thư mục"""
        try:
            image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']
            
            for file in os.listdir(folder_path):
                if any(file.lower().endswith(ext) for ext in image_extensions):
                    return os.path.join(folder_path, file)
            
            return None
        except Exception as e:
            self.logger.error(f"Lỗi tìm ảnh trong {folder_path}: {str(e)}")
            return None
    
    def generate_content_for_folder(self, folder_path: str, title_prompt: str, description_prompt: str):
        """Tạo nội dung cho thư mục"""
        try:
            if not self.api_key:
                self.error_occurred.emit(folder_path, "API key chưa được cấu hình")
                return
            
            # Tìm ảnh đầu tiên
            first_image = self.find_first_image(folder_path)
            if not first_image:
                self.error_occurred.emit(folder_path, "Không tìm thấy ảnh trong thư mục")
                return
            
            # Encode ảnh
            image_base64 = self.encode_image_to_base64(first_image)
            if not image_base64:
                self.error_occurred.emit(folder_path, "Không thể đọc ảnh")
                return
            
            folder_name = os.path.basename(folder_path)
            
            # Thay thế variables trong prompts
            title_prompt_filled = title_prompt.replace("{folder_name}", folder_name)
            description_prompt_filled = description_prompt.replace("{folder_name}", folder_name)
            
            # Tạo tiêu đề
            title = self._generate_text_with_image(image_base64, first_image, title_prompt_filled)
            if not title:
                self.error_occurred.emit(folder_path, "Không thể tạo tiêu đề")
                return
            
            # Tạo mô tả
            description = self._generate_text_with_image(image_base64, first_image, description_prompt_filled)
            if not description:
                self.error_occurred.emit(folder_path, "Không thể tạo mô tả")
                return
            
            result = {
                'title': title.strip(),
                'description': description.strip(),
                'image_used': first_image
            }
            
            self.content_generated.emit(folder_path, result)
            
        except Exception as e:
            self.error_occurred.emit(folder_path, f"Lỗi tạo nội dung: {str(e)}")
    
    def _generate_text_with_image(self, image_base64: str, image_path: str, prompt: str) -> Optional[str]:
        """Tạo text từ ảnh và prompt với tự động xoay API key"""
        max_retries = len(self.api_keys) if self.api_keys else 1
        
        for retry in range(max_retries):
            current_key = self.get_current_api_key()
            if not current_key:
                self.logger.error("Không có API key khả dụng")
                return None
            
            try:
                url = f"{self.base_url}?key={current_key}"
                
                mime_type = self.get_image_mime_type(image_path)
                
                data = {
                    "contents": [{
                        "parts": [
                            {"text": prompt},
                            {
                                "inline_data": {
                                    "mime_type": mime_type,
                                    "data": image_base64
                                }
                            }
                        ]
                    }]
                }
                
                response = requests.post(url, json=data, timeout=30)
                
                if response.status_code == 200:
                    result = response.json()
                    if 'candidates' in result and len(result['candidates']) > 0:
                        text = result['candidates'][0]['content']['parts'][0]['text']
                        self.logger.info(f"API call successful with key #{self.current_key_index + 1}")
                        return text
                    else:
                        self.logger.error("Không có kết quả từ API")
                        return None
                
                elif response.status_code in [429, 403]:
                    # Quota exceeded or forbidden - try next key
                    try:
                        error_data = response.json()
                        error_message = str(error_data).lower()
                        if any(keyword in error_message for keyword in ['quota', 'limit', 'exceeded', 'forbidden']):
                            self.logger.warning(f"API key #{self.current_key_index + 1} quota exceeded, rotating to next key")
                            self.rotate_api_key()
                            if not self.has_available_keys():
                                self.logger.error("Tất cả API keys đã hết quota")
                                return None
                            continue
                    except:
                        pass
                    
                    self.logger.error(f"API error: {response.status_code} - {response.text}")
                    return None
                
                else:
                    self.logger.error(f"API error: {response.status_code} - {response.text}")
                    # Don't rotate on other errors, might be temporary
                    return None
                    
            except Exception as e:
                self.logger.error(f"Lỗi gọi API với key #{self.current_key_index + 1}: {str(e)}")
                if retry < max_retries - 1:
                    self.rotate_api_key()
                    continue
                return None
        
        self.logger.error("Đã thử tất cả API keys nhưng không thành công")
        return None
