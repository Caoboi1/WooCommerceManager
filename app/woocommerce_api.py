#!/usr/bin/env python3
"""
WooCommerce API Client với WordPress Authentication
Hỗ trợ upload media và tạo sản phẩm với ảnh
"""

import requests
import logging
from typing import Dict, List, Optional, Tuple, Any
import os
import mimetypes
from requests.auth import HTTPBasicAuth
import base64

class WooCommerceAPI:
    """WooCommerce REST API Client với WordPress Authentication"""

    def __init__(self, site):
        self.site = site
        self.base_url = site.url.rstrip('/')
        self.consumer_key = site.consumer_key
        self.consumer_secret = site.consumer_secret

        # WordPress Authentication (nếu có)
        self.wp_username = getattr(site, 'wp_username', None)
        self.wp_app_password = getattr(site, 'wp_app_password', None)

        self.session = requests.Session()
        self.session.auth = (self.consumer_key, self.consumer_secret)

        # Timeout và retry settings
        self.timeout = 30
        self.max_retries = 3

        self.logger = logging.getLogger(__name__)

    def _make_request(self, method: str, endpoint: str, data: Dict = None, 
                     params: Dict = None, files: Dict = None, 
                     use_wp_auth: bool = False) -> requests.Response:
        """Thực hiện HTTP request với error handling"""
        url = f"{self.base_url}/wp-json/wc/v3/{endpoint}"

        # Sử dụng WordPress auth cho media uploads
        if use_wp_auth and self.wp_username and self.wp_app_password:
            auth = HTTPBasicAuth(self.wp_username, self.wp_app_password)
        else:
            auth = (self.consumer_key, self.consumer_secret)

        headers = {}
        if not files:  # Không set Content-Type khi upload file
            headers['Content-Type'] = 'application/json'

        for attempt in range(self.max_retries):
            try:
                response = requests.request(
                    method=method,
                    url=url,
                    json=data if not files else None,
                    params=params,
                    files=files,
                    auth=auth,
                    headers=headers,
                    timeout=self.timeout,
                    verify=True
                )

                self.logger.debug(f"{method} {url} - Status: {response.status_code}")
                return response

            except requests.exceptions.RequestException as e:
                self.logger.warning(f"Attempt {attempt + 1} failed: {str(e)}")
                if attempt == self.max_retries - 1:
                    raise

        raise Exception("Max retries exceeded")

    def test_connection(self) -> Tuple[bool, str]:
        """Test kết nối WooCommerce API"""
        try:
            # Thử lấy thông tin system status trước
            response = self._make_request('GET', 'system_status')

            if response.status_code == 200:
                data = response.json()

                # Thử lấy tên store từ nhiều nguồn khác nhau
                store_name = None

                # Nguồn 1: Từ settings general
                if data.get('settings', {}).get('general'):
                    general_settings = data['settings']['general']
                    store_name = (general_settings.get('woocommerce_store_name') or 
                                general_settings.get('blogname') or 
                                general_settings.get('woocommerce_default_customer_address'))

                # Nguồn 2: Thử lấy từ site info
                if not store_name or store_name == 'Unknown':
                    try:
                        site_response = self._make_request('GET', '../wp/v2/settings', use_wp_auth=True)
                        if site_response.status_code == 200:
                            site_data = site_response.json()
                            store_name = site_data.get('title', site_data.get('name'))
                    except:
                        pass

                # Nguồn 3: Sử dụng domain name từ URL
                if not store_name or store_name == 'Unknown':
                    from urllib.parse import urlparse
                    parsed_url = urlparse(self.base_url)
                    store_name = parsed_url.netloc or self.site.name

                # Fallback cuối cùng
                if not store_name:
                    store_name = self.site.name or "WooCommerce Store"

                return True, f"Kết nối thành công với store: {store_name}"

            elif response.status_code == 401:
                return False, "Lỗi xác thực: Consumer Key/Secret không đúng"
            elif response.status_code == 404:
                return False, "Lỗi 404: WooCommerce REST API không được kích hoạt hoặc URL không đúng"
            else:
                return False, f"Lỗi kết nối: HTTP {response.status_code}"

        except requests.exceptions.SSLError:
            return False, "Lỗi SSL: Không thể xác minh chứng chỉ SSL"
        except requests.exceptions.ConnectionError:
            return False, "Lỗi kết nối: Không thể kết nối đến server"
        except requests.exceptions.Timeout:
            return False, "Lỗi timeout: Server không phản hồi"
        except Exception as e:
            return False, f"Lỗi không xác định: {str(e)}"

    def get_products(self, per_page: int = 10, page: int = 1, **kwargs) -> List[Dict]:
        """Lấy danh sách sản phẩm"""
        try:
            params = {
                'per_page': per_page,
                'page': page,
                **kwargs
            }

            response = self._make_request('GET', 'products', params=params)
            response.raise_for_status()

            return response.json()

        except Exception as e:
            self.logger.error(f"Lỗi lấy sản phẩm: {str(e)}")
            return []

    def get_all_products(self, per_page: int = 100) -> List[Dict]:
        """Lấy tất cả sản phẩm từ site với pagination"""
        all_products = []
        page = 1

        try:
            while True:
                products = self.get_products(per_page=per_page, page=page)

                if not products:
                    break

                all_products.extend(products)

                # Nếu số sản phẩm trả về ít hơn per_page, có nghĩa là đã hết
                if len(products) < per_page:
                    break

                page += 1

                # Giới hạn để tránh vòng lặp vô tận
                if page > 100:  # Tối đa 10,000 sản phẩm
                    self.logger.warning("Đã đạt giới hạn 10,000 sản phẩm")
                    break

            self.logger.info(f"Đã lấy {len(all_products)} sản phẩm từ {page-1} trang")
            return all_products

        except Exception as e:
            self.logger.error(f"Lỗi lấy tất cả sản phẩm: {str(e)}")
            return all_products  # Trả về những gì đã lấy được

    def get_categories(self, per_page: int = 100) -> List[Dict]:
        """Lấy danh sách categories"""
        try:
            params = {'per_page': per_page}
            response = self._make_request('GET', 'products/categories', params=params)
            response.raise_for_status()

            return response.json()

        except Exception as e:
            self.logger.error(f"Lỗi lấy categories: {str(e)}")
            return []

    def upload_media(self, image_path: str, title: str = None, alt_text: str = None, description: str = None, post_id: int = None) -> Optional[Dict]:
        """Upload ảnh lên WordPress Media Library với khả năng attach vào post"""
        try:
            # Đảm bảo image_path là string path, không phải dict
            if isinstance(image_path, dict):
                raise ValueError("upload_media expects file path string, not dict")

            if not os.path.exists(image_path):
                raise FileNotFoundError(f"File không tồn tại: {image_path}")

            # Xác định MIME type
            mime_type, _ = mimetypes.guess_type(image_path)
            if not mime_type or not mime_type.startswith('image/'):
                raise ValueError(f"File không phải là ảnh: {image_path}")

            filename = os.path.basename(image_path)
            if not title:
                title = os.path.splitext(filename)[0]

            # Chuẩn bị data cho WordPress Media API
            url = f"{self.base_url}/wp-json/wp/v2/media"

            # WordPress authentication required for media upload
            if not (self.wp_username and self.wp_app_password):
                raise Exception("Cần WordPress username và app password để upload media")

            headers = {
                'Content-Disposition': f'attachment; filename={filename}',
                'Content-Type': mime_type,
            }

            # Read file content
            with open(image_path, 'rb') as f:
                file_content = f.read()

            # Upload với WordPress auth
            auth = HTTPBasicAuth(self.wp_username, self.wp_app_password)

            # Thêm post_id vào URL nếu có để attach ảnh
            params = {}
            if post_id:
                params['post'] = post_id

            response = requests.post(
                url,
                headers=headers,
                data=file_content,
                auth=auth,
                params=params,
                timeout=self.timeout
            )

            if response.status_code == 201:
                media_data = response.json()
                media_id = media_data.get('id')

                # Cập nhật metadata với Caption và Description
                if media_id:
                    try:
                        update_url = f"{self.base_url}/wp-json/wp/v2/media/{media_id}"
                        update_data = {}

                        # Caption sử dụng title (tên sản phẩm)
                        if title:
                            update_data['caption'] = title

                        # Alternative Text
                        if alt_text:
                            update_data['alt_text'] = alt_text

                        # Description sử dụng mô tả sản phẩm
                        if description:
                            update_data['description'] = description

                        if update_data:
                            self.logger.info(f"🔧 Updating media metadata for {filename}: Caption='{title}', Alt='{alt_text}', Description='{description[:50]}...'")

                            # Use Basic Auth with WordPress credentials
                            try:
                                update_response = requests.post(
                                    update_url,
                                    auth=HTTPBasicAuth(self.wp_username, self.wp_app_password),
                                    json=update_data,
                                    headers={'Content-Type': 'application/json'},
                                    timeout=self.timeout
                                )

                                if update_response.status_code == 200:
                                    updated_media = update_response.json()
                                    self.logger.info(f"✅ Successfully updated media metadata for {filename}")
                                    self.logger.info(f"   Caption: {updated_media.get('caption', {}).get('rendered', 'Not set')}")
                                    self.logger.info(f"   Alt Text: {updated_media.get('alt_text', 'Not set')}")
                                    self.logger.info(f"   Description: {updated_media.get('description', {}).get('rendered', 'Not set')[:50]}...")
                                else:
                                    self.logger.warning(f"❌ Failed to update media metadata: HTTP {update_response.status_code}")
                                    try:
                                        error_data = update_response.json()
                                        self.logger.warning(f"   Error: {error_data.get('message', 'Unknown error')}")
                                    except:
                                        self.logger.warning(f"   Response: {update_response.text[:200]}")

                            except Exception as e:
                                self.logger.error(f"❌ Exception updating media metadata for {filename}: {str(e)}")

                    except Exception as e:
                        self.logger.error(f"❌ Error preparing media metadata update for {filename}: {str(e)}")

                # Return formatted media data cho WooCommerce
                return {
                    'id': media_id,
                    'src': media_data.get('source_url', ''),
                    'name': media_data.get('title', {}).get('rendered', filename),
                    'alt': alt_text or title or '',
                    'position': 0  # WooCommerce image position
                }
            else:
                error_msg = f"HTTP {response.status_code}"
                try:
                    error_data = response.json()
                    error_msg = error_data.get('message', error_msg)
                except:
                    pass
                raise Exception(f"Upload thất bại: {error_msg}")

        except Exception as e:
            self.logger.error(f"Lỗi upload media: {str(e)}")
            raise

    def create_product(self, product_data: Dict) -> Optional[Dict]:
        """Tạo sản phẩm mới với improved error handling"""
        try:
            # Validate và clean images data trước khi tạo sản phẩm
            cleaned_product_data = product_data.copy()
            if 'images' in cleaned_product_data:
                valid_images = []
                for image in cleaned_product_data['images']:
                    if isinstance(image, dict) and image.get('id') and image.get('src'):
                        # Validate image ID exists
                        image_id = image.get('id')
                        if isinstance(image_id, int) and image_id > 0:
                            valid_images.append({
                                'id': image_id,
                                'src': image.get('src'),
                                'name': image.get('name', ''),
                                'alt': image.get('alt', ''),
                                'position': len(valid_images)
                            })
                        else:
                            self.logger.warning(f"Skipping invalid image ID: {image_id}")

                if valid_images:
                    cleaned_product_data['images'] = valid_images
                    self.logger.info(f"Using {len(valid_images)} valid images out of {len(product_data.get('images', []))}")
                else:
                    # Remove images if none are valid
                    cleaned_product_data.pop('images', None)
                    self.logger.warning("No valid images found, creating product without images")

            # Categories - ensure ID is integer
            categories = cleaned_product_data.get('categories')
            if categories:
                if isinstance(categories, (list, tuple)):
                    cleaned_product_data['categories'] = []
                    for cat_id in categories:
                        if cat_id:
                            try:
                                # Convert to integer to ensure proper type
                                cat_id_int = int(cat_id)
                                cleaned_product_data['categories'].append({'id': cat_id_int})
                            except (ValueError, TypeError):
                                self.logger.warning(f"Invalid category ID: {cat_id}")
                                continue
                elif isinstance(categories, (int, str)):
                    try:
                        cat_id_int = int(categories)
                        cleaned_product_data['categories'] = [{'id': cat_id_int}]
                    except (ValueError, TypeError):
                        self.logger.warning(f"Invalid category ID: {categories}")
                        cleaned_product_data['categories'] = []

            # Log request data for debugging
            self.logger.debug(f"Creating product with cleaned data: {cleaned_product_data}")

            response = self._make_request('POST', 'products', data=cleaned_product_data)

            if response.status_code == 201:
                result = response.json()
                product_id = result.get('id')
                self.logger.info(f"Tạo sản phẩm thành công: ID {product_id}")

                # Attach ảnh vào sản phẩm để không còn hiển thị (Unattached)
                if cleaned_product_data.get('images') and self.wp_username and self.wp_app_password:
                    for image in cleaned_product_data.get('images', []):
                        media_id = image.get('id')
                        if media_id and isinstance(media_id, int):
                            try:
                                self.attach_media_to_post(media_id, product_id)
                            except Exception as e:
                                self.logger.warning(f"Không thể attach ảnh {media_id}: {str(e)}")

                return result
            else:
                # Enhanced error handling
                error_msg = f"HTTP {response.status_code}"
                try:
                    error_data = response.json()
                    if 'message' in error_data:
                        error_msg = error_data['message']
                    elif 'data' in error_data and 'status' in error_data['data']:
                        error_msg = f"{error_data.get('message', 'Unknown error')} (Status: {error_data['data']['status']})"
                except:
                    error_msg = response.text[:200] if response.text else f"HTTP {response.status_code}"

                self.logger.error(f"Lỗi tạo sản phẩm: {error_msg}")
                self.logger.error(f"Response content: {response.text[:500]}")
                raise Exception(f"Không thể tạo sản phẩm: {error_msg}")

        except requests.exceptions.HTTPError as e:
            self.logger.error(f"HTTP Error: {str(e)}")
            raise Exception(f"Không thể tạo sản phẩm: {str(e)}")
        except Exception as e:
            self.logger.error(f"Lỗi tạo sản phẩm: {str(e)}")
            raise Exception(f"Không thể tạo sản phẩm: {str(e)}")

    def update_product(self, product_id: int, product_data: Dict) -> Optional[Dict]:
        """Cập nhật sản phẩm"""
        try:
            response = self._make_request('PUT', f'products/{product_id}', data=product_data)
            response.raise_for_status()

            result = response.json()
            self.logger.info(f"Cập nhật sản phẩm thành công: ID {product_id}")
            return result

        except Exception as e:
            self.logger.error(f"Lỗi cập nhật sản phẩm {product_id}: {str(e)}")
            raise

    def delete_product(self, product_id: int, force: bool = True) -> bool:
        """Xóa sản phẩm"""
        try:
            params = {'force': force}
            response = self._make_request('DELETE', f'products/{product_id}', params=params)

            if response.status_code in [200, 202]:
                result = response.json()
                self.logger.info(f"Xóa sản phẩm thành công: ID {product_id}")
                return True
            elif response.status_code == 404:
                self.logger.warning(f"Sản phẩm {product_id} không tồn tại trên WooCommerce")
                return True  # Coi như đã xóa thành công
            else:
                error_msg = f"HTTP {response.status_code}"
                try:
                    error_data = response.json()
                    error_msg = error_data.get('message', error_msg)
                except:
                    pass
                self.logger.error(f"Lỗi xóa sản phẩm {product_id}: {error_msg}")
                return False

        except Exception as e:
            self.logger.error(f"Lỗi xóa sản phẩm {product_id}: {str(e)}")
            return False

    def create_category(self, category_data: Dict) -> Optional[Dict]:
        """Tạo category mới với improved error handling"""
        try:
            # Validate và clean category data trước khi gửi
            cleaned_data = self._validate_category_data(category_data)

            # Log request data for debugging
            self.logger.debug(f"Creating category with data: {cleaned_data}")

            response = self._make_request('POST', 'products/categories', data=cleaned_data)

            if response.status_code == 201:
                result = response.json()
                category_id = result.get('id')
                self.logger.info(f"Tạo category thành công: ID {category_id}")
                return result
            else:
                # Enhanced error handling
                error_msg = f"HTTP {response.status_code}"
                try:
                    error_data = response.json()
                    if 'message' in error_data:
                        error_msg = error_data['message']
                    elif 'data' in error_data:
                        error_details = error_data.get('data', {})
                        if 'status' in error_details:
                            error_msg = f"{error_data.get('message', 'Unknown error')} (Status: {error_details['status']})"
                        if 'params' in error_details:
                            error_msg += f" - Invalid params: {error_details['params']}"
                except:
                    error_msg = response.text[:200] if response.text else f"HTTP {response.status_code}"

                self.logger.error(f"Lỗi tạo category: {error_msg}")
                self.logger.error(f"Response content: {response.text[:500]}")

                # Xử lý các lỗi cụ thể
                if response.status_code == 500:
                    if "duplicate" in error_msg.lower() or "already exists" in error_msg.lower():
                        raise Exception(f"Category đã tồn tại: {cleaned_data.get('name', 'Unknown')}")
                    else:
                        raise Exception(f"Lỗi server khi tạo category. Kiểm tra lại dữ liệu: {error_msg}")
                elif response.status_code == 400:
                    raise Exception(f"Dữ liệu category không hợp lệ: {error_msg}")
                elif response.status_code == 401:
                    raise Exception("Lỗi xác thực: Consumer Key/Secret không đúng hoặc không có quyền tạo category")
                elif response.status_code == 403:
                    raise Exception("Consumer Key không có quyền tạo category. Cần quyền 'Read/Write'")
                else:
                    raise Exception(f"Không thể tạo category: {error_msg}")

        except requests.exceptions.HTTPError as e:
            self.logger.error(f"HTTP Error: {str(e)}")
            raise Exception(f"Không thể tạo category: {str(e)}")
        except Exception as e:
            if "category" in str(e).lower():
                raise  # Re-raise category-specific errors
            self.logger.error(f"Lỗi tạo category: {str(e)}")
            raise Exception(f"Không thể tạo category: {str(e)}")

    def _validate_category_data(self, category_data: Dict) -> Dict:
        """Validate và clean category data"""
        cleaned_data = {}

        # Name là required
        if not category_data.get('name'):
            raise ValueError("Tên category không được để trống")

        cleaned_data['name'] = str(category_data['name']).strip()

        # Slug - tự tạo nếu không có
        if category_data.get('slug'):
            cleaned_data['slug'] = str(category_data['slug']).strip().lower()
        else:
            # Tạo slug từ name
            import re
            slug = re.sub(r'[^a-zA-Z0-9\s-]', '', cleaned_data['name'].lower())
            slug = re.sub(r'\s+', '-', slug.strip())
            cleaned_data['slug'] = slug

        # Description
        if category_data.get('description'):
            cleaned_data['description'] = str(category_data['description']).strip()

        # Parent ID
        if category_data.get('parent') or category_data.get('parent_id'):
            parent_id = category_data.get('parent') or category_data.get('parent_id')
            if parent_id and parent_id != 0:
                cleaned_data['parent'] = int(parent_id)

        # Image
        if category_data.get('image'):
            image_data = category_data['image']
            if isinstance(image_data, dict):
                cleaned_data['image'] = image_data
            elif isinstance(image_data, str):
                cleaned_data['image'] = {'src': image_data}

        # Display type
        if category_data.get('display'):
            cleaned_data['display'] = str(category_data['display'])

        # Menu order
        if category_data.get('menu_order'):
            cleaned_data['menu_order'] = int(category_data['menu_order'])

        return cleaned_data

    def update_category(self, category_id: int, category_data: Dict) -> Optional[Dict]:
        """Cập nhật category"""
        try:
            response = self._make_request('PUT', f'products/categories/{category_id}', data=category_data)
            response.raise_for_status()

            result = response.json()
            self.logger.info(f"Cập nhật category thành công: ID {category_id}")
            return result

        except Exception as e:
            self.logger.error(f"Lỗi cập nhật category {category_id}: {str(e)}")
            raise

    def delete_category(self, category_id: int, force: bool = True) -> bool:
        """Xóa category"""
        try:
            params = {'force': force}
            response = self._make_request('DELETE', f'products/categories/{category_id}', params=params)
            response.raise_for_status()

            self.logger.info(f"Xóa category thành công: ID {category_id}")
            return True

        except Exception as e:
            self.logger.error(f"Lỗi xóa category {category_id}: {str(e)}")
            return False

    def get_product_by_id(self, product_id: int) -> Optional[Dict]:
        """Lấy thông tin sản phẩm theo ID"""
        try:
            response = self._make_request('GET', f'products/{product_id}')
            response.raise_for_status()

            return response.json()

        except Exception as e:
            self.logger.error(f"Lỗi lấy sản phẩm {product_id}: {str(e)}")
            return None

    def batch_create_products(self, products_data: List[Dict]) -> List[Dict]:
        """Tạo nhiều sản phẩm cùng lúc"""
        try:
            batch_data = {
                'create': products_data
            }

            response = self._make_request('POST', 'products/batch', data=batch_data)
            response.raise_for_status()

            result = response.json()
            created_products = result.get('create', [])

            self.logger.info(f"Tạo {len(created_products)} sản phẩm thành công")
            return created_products

        except Exception as e:
            self.logger.error(f"Lỗi tạo batch sản phẩm: {str(e)}")
            raise

    def search_products(self, search_term: str, per_page: int = 10) -> List[Dict]:
        """Tìm kiếm sản phẩm"""
        try:
            params = {
                'search': search_term,
                'per_page': per_page
            }

            response = self._make_request('GET', 'products', params=params)
            response.raise_for_status()

            return response.json()

        except Exception as e:
            self.logger.error(f"Lỗi tìm kiếm sản phẩm: {str(e)}")
            return []

    def get_product_variations(self, product_id: int) -> List[Dict]:
        """Lấy danh sách variations của sản phẩm"""
        try:
            response = self._make_request('GET', f'products/{product_id}/variations')
            response.raise_for_status()

            return response.json()

        except Exception as e:
            self.logger.error(f"Lỗi lấy variations: {str(e)}")
            return []

    def update_media_metadata(self, media_id: int, title: str = None, alt_text: str = None, description: str = None) -> bool:
        """Cập nhật metadata cho ảnh đã upload"""
        try:
            if not media_id:
                self.logger.error("Media ID không hợp lệ")
                return False

            if not (self.wp_username and self.wp_app_password):
                self.logger.warning("Cần WordPress credentials để cập nhật metadata")
                return False

            update_url = f"{self.base_url}/wp-json/wp/v2/media/{media_id}"
            update_data = {}

            # Cập nhật Caption từ title
            if title:
                update_data['caption'] = title

            # Cập nhật Alternative Text
            if alt_text:
                update_data['alt_text'] = alt_text

            # Cập nhật Description từ mô tả sản phẩm
            if description:
                update_data['description'] = description

            if not update_data:
                self.logger.info("Không có metadata nào để cập nhật")
                return True

            self.logger.info(f"🔧 Updating metadata for media {media_id}")
            self.logger.info(f"   Caption: '{title}'")
            self.logger.info(f"   Alt Text: '{alt_text}'")
            self.logger.info(f"   Description: '{description[:50] if description else ''}...'")

            # Sử dụng WordPress Auth để cập nhật
            response = requests.post(
                update_url,
                auth=HTTPBasicAuth(self.wp_username, self.wp_app_password),
                json=update_data,
                headers={'Content-Type': 'application/json'},
                timeout=self.timeout
            )

            if response.status_code == 200:
                updated_media = response.json()
                self.logger.info(f"✅ Media {media_id} metadata updated successfully")

                # Log kết quả cập nhật
                caption = updated_media.get('caption', {})
                if isinstance(caption, dict):
                    caption_text = caption.get('rendered', 'Not set')
                else:
                    caption_text = str(caption) if caption else 'Not set'

                description_obj = updated_media.get('description', {})
                if isinstance(description_obj, dict):
                    description_text = description_obj.get('rendered', 'Not set')
                else:
                    description_text = str(description_obj) if description_obj else 'Not set'

                self.logger.info(f"   Updated Caption: {caption_text}")
                self.logger.info(f"   Updated Alt Text: {updated_media.get('alt_text', 'Not set')}")
                self.logger.info(f"   Updated Description: {description_text[:50]}...")

                return True
            else:
                self.logger.warning(f"❌ Failed to update media metadata: HTTP {response.status_code}")
                try:
                    error_data = response.json()
                    self.logger.warning(f"   Error: {error_data.get('message', 'Unknown error')}")
                except:
                    self.logger.warning(f"   Response: {response.text[:200]}")
                return False

        except Exception as e:
            self.logger.error(f"❌ Exception updating media metadata: {str(e)}")
            return False

    def attach_media_to_post(self, media_id: int, post_id: int) -> bool:
        """Attach ảnh vào sản phẩm để không còn hiển thị (Unattached)"""
        try:
            # Validate inputs
            if not media_id or not post_id:
                self.logger.error(f"Invalid media_id ({media_id}) or post_id ({post_id})")
                return False

            # Sử dụng WordPress API để attach media
            url = f"{self.base_url}/wp-json/wp/v2/media/{media_id}"

            # Chỉ gửi post ID, không gửi status để tránh lỗi
            data = {
                'post': post_id
            }

            auth = HTTPBasicAuth(self.wp_username, self.wp_app_password)

            headers = {
                'Content-Type': 'application/json'
            }

            # Use POST method để update media attachment
            response = requests.post(
                url,
                json=data,
                auth=auth,
                headers=headers,
                timeout=self.timeout
            )

            if response.status_code in [200, 201]:
                self.logger.info(f"Đã attach media {media_id} vào post {post_id}")
                return True
            else:
                # Log chi tiết để debug
                self.logger.warning(f"Không thể attach media {media_id}: HTTP {response.status_code}")
                try:
                    error_data = response.json()
                    self.logger.warning(f"Error response: {error_data}")
                except:
                    self.logger.warning(f"Response text: {response.text[:200]}")
                return False

        except Exception as e:
            self.logger.error(f"Lỗi attach media {media_id} to post {post_id}: {str(e)}")
            return False

    # WordPress Pages API Methods
    def get_pages(self, per_page: int = 100, page: int = 1, **kwargs) -> List[Dict]:
        """Lấy danh sách pages từ WordPress"""
        try:
            url = f"{self.base_url}/wp-json/wp/v2/pages"

            params = {'per_page': per_page,
                'page': page,
                **kwargs
            }

            # Sử dụng WordPress auth
            auth = HTTPBasicAuth(self.wp_username, self.wp_app_password) if self.wp_username and self.wp_app_password else (self.consumer_key, self.consumer_secret)

            response = requests.get(
                url,
                params=params,
                auth=auth,
                timeout=self.timeout
            )

            response.raise_for_status()
            return response.json()

        except Exception as e:
            self.logger.error(f"Lỗi lấy pages: {str(e)}")
            return []

    def get_page_by_id(self, page_id: int) -> Optional[Dict]:
        """Lấy thông tin page theo ID"""
        try:
            url = f"{self.base_url}/wp-json/wp/v2/pages/{page_id}"

            auth = HTTPBasicAuth(self.wp_username, self.wp_app_password) if self.wp_username and self.wp_app_password else (self.consumer_key, self.consumer_secret)

            response = requests.get(
                url,
                auth=auth,
                timeout=self.timeout
            )

            response.raise_for_status()
            return response.json()

        except Exception as e:
            self.logger.error(f"Lỗi lấy page {page_id}: {str(e)}")
            return None

    def create_page(self, page_data: Dict) -> Optional[Dict]:
        """Tạo page mới"""
        try:
            url = f"{self.base_url}/wp-json/wp/v2/pages"

            # WordPress authentication required
            if not (self.wp_username and self.wp_app_password):
                raise Exception("Cần WordPress username và app password để tạo page")

            auth = HTTPBasicAuth(self.wp_username, self.wp_app_password)

            headers = {
                'Content-Type': 'application/json'
            }

            response = requests.post(
                url,
                json=page_data,
                auth=auth,
                headers=headers,
                timeout=self.timeout
            )

            if response.status_code == 201:
                result = response.json()
                self.logger.info(f"Tạo page thành công: ID {result.get('id')}")
                return result
            else:
                error_msg = f"HTTP {response.status_code}"
                try:
                    error_data = response.json()
                    error_msg = error_data.get('message', error_msg)
                except:
                    pass
                raise Exception(f"Không thể tạo page: {error_msg}")

        except Exception as e:
            self.logger.error(f"Lỗi tạo page: {str(e)}")
            raise

    def update_page(self, page_id: int, page_data: Dict) -> Optional[Dict]:
        """Cập nhật page"""
        try:
            url = f"{self.base_url}/wp-json/wp/v2/pages/{page_id}"

            # WordPress authentication required
            if not (self.wp_username and self.wp_app_password):
                raise Exception("Cần WordPress username và app password để cập nhật page")

            auth = HTTPBasicAuth(self.wp_username, self.wp_app_password)

            headers = {
                'Content-Type': 'application/json'
            }

            response = requests.post(
                url,
                json=page_data,
                auth=auth,
                headers=headers,
                timeout=self.timeout
            )

            if response.status_code == 200:
                result = response.json()
                self.logger.info(f"Cập nhật page thành công: ID {page_id}")
                return result
            else:
                error_msg = f"HTTP {response.status_code}"
                try:
                    error_data = response.json()
                    error_msg = error_data.get('message', error_msg)
                except:
                    pass
                raise Exception(f"Không thể cập nhật page: {error_msg}")

        except Exception as e:
            self.logger.error(f"Lỗi cập nhật page {page_id}: {str(e)}")
            raise

    def delete_page(self, page_id: int, force: bool = True) -> bool:
        """Xóa page"""
        try:
            url = f"{self.base_url}/wp-json/wp/v2/pages/{page_id}"

            # WordPress authentication required
            if not (self.wp_username and self.wp_app_password):
                raise Exception("Cần WordPress username và app password để xóa page")

            auth = HTTPBasicAuth(self.wp_username, self.wp_app_password)

            params = {'force': force}

            response = requests.delete(
                url,
                params=params,
                auth=auth,
                timeout=self.timeout
            )

            if response.status_code == 200:
                self.logger.info(f"Xóa page thành công: ID {page_id}")
                return True
            else:
                error_msg = f"HTTP {response.status_code}"
                try:
                    error_data = response.json()
                    error_msg = error_data.get('message', error_msg)
                except:
                    pass
                self.logger.error(f"Không thể xóa page: {error_msg}")
                return False

        except Exception as e:
            self.logger.error(f"Lỗi xóa page {page_id}: {str(e)}")
            return False