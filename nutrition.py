import math  # Thêm import này ở đầu file nutrition.py
from typing import Dict, Optional, List

# Database dinh dưỡng các món ăn Việt Nam (mỗi khẩu phần ~300-400g)
NUTRITION_DATABASE = {
    'Pho': {
        'calories': 350,
        'protein': 15,
        'carbs': 50,
        'fat': 8,
        'fiber': 3,
        'sodium': 1200,
        'benefits': ['Đầy đủ dinh dưỡng', 'Giàu protein', 'Nước dùng bổ dưỡng'],
    },
    'Banh mi': {
        'calories': 400,
        'protein': 18,
        'carbs': 45,
        'fat': 15,
        'fiber': 2,
        'sodium': 800,
        'benefits': ['Tiện lợi', 'Đa dạng dinh dưỡng', 'Ngon miệng'],
    },
    'Com tam': {
        'calories': 450,
        'protein': 20,
        'carbs': 60,
        'fat': 12,
        'fiber': 2,
        'sodium': 900,
        'benefits': ['Nhiều năng lượng', 'Giàu protein', 'Đầy bụng'],
    },
    'Bun bo Hue': {
        'calories': 420,
        'protein': 22,
        'carbs': 48,
        'fat': 14,
        'fiber': 3,
        'sodium': 1500,
        'benefits': ['Cay nóng', 'Giàu protein', 'Kích thích tiêu hóa'],
    },
    'Goi cuon': {
        'calories': 150,
        'protein': 8,
        'carbs': 20,
        'fat': 4,
        'fiber': 2,
        'sodium': 400,
        'benefits': ['Ít calo', 'Tươi mát', 'Nhiều rau sống'],
    },
    'Banh xeo': {
        'calories': 320,
        'protein': 12,
        'carbs': 35,
        'fat': 14,
        'fiber': 2,
        'sodium': 700,
        'benefits': ['Giòn ngon', 'Nhiều rau', 'Protein từ tôm thịt'],
    },
    'Banh cuon': {
        'calories': 200,
        'protein': 10,
        'carbs': 30,
        'fat': 5,
        'fiber': 1,
        'sodium': 600,
        'benefits': ['Nhẹ nhàng', 'Dễ tiêu hóa', 'Ít dầu mỡ'],
    },
    'Hu tieu': {
        'calories': 380,
        'protein': 16,
        'carbs': 52,
        'fat': 10,
        'fiber': 2,
        'sodium': 1100,
        'benefits': ['Nước dùng ngọt', 'Đa dạng topping', 'Đầy đủ dinh dưỡng'],
    },
    'Cao lau': {
        'calories': 400,
        'protein': 18,
        'carbs': 55,
        'fat': 12,
        'fiber': 3,
        'sodium': 900,
        'benefits': ['Đặc sản Hội An', 'Độc đáo', 'Giàu hương vị'],
    },
    'Banh beo': {
        'calories': 180,
        'protein': 6,
        'carbs': 28,
        'fat': 5,
        'fiber': 1,
        'sodium': 500,
        'benefits': ['Nhẹ nhàng', 'Đặc sản Huế', 'Dễ ăn'],
    },
    'Banh bot loc': {
        'calories': 220,
        'protein': 8,
        'carbs': 32,
        'fat': 7,
        'fiber': 1.5,
        'sodium': 550,
        'benefits': ['Dai ngon', 'Giàu protein từ tôm', 'Đặc sản miền Trung'],
    },
    'Banh can': {
        'calories': 160,
        'protein': 7,
        'carbs': 22,
        'fat': 5,
        'fiber': 1,
        'sodium': 450,
        'benefits': ['Nhỏ gọn', 'Thơm ngon', 'Đặc sản miền Trung'],
    },
    'Banh canh': {
        'calories': 300,
        'protein': 14,
        'carbs': 42,
        'fat': 8,
        'fiber': 2,
        'sodium': 1000,
        'benefits': ['Sợi dai', 'Nước dùng đậm đà', 'Đầy bụng'],
    },
    'Banh chung': {
        'calories': 380,
        'protein': 12,
        'carbs': 65,
        'fat': 8,
        'fiber': 3,
        'sodium': 600,
        'benefits': ['Truyền thống Tết', 'Giàu năng lượng', 'Lâu no'],
    },
    'Banh duc': {
        'calories': 140,
        'protein': 5,
        'carbs': 25,
        'fat': 3,
        'fiber': 1,
        'sodium': 400,
        'benefits': ['Mát mẻ', 'Ít calo', 'Dễ tiêu'],
    },
    'Banh gio': {
        'calories': 250,
        'protein': 10,
        'carbs': 38,
        'fat': 7,
        'fiber': 2,
        'sodium': 650,
        'benefits': ['Tiện lợi', 'Đầy bụng', 'Thơm lá chuối'],
    },
    'Banh khot': {
        'calories': 280,
        'protein': 11,
        'carbs': 32,
        'fat': 12,
        'fiber': 1.5,
        'sodium': 600,
        'benefits': ['Giòn tan', 'Đặc sản Vũng Tàu', 'Nhiều topping'],
    },
    'Banh pia': {
        'calories': 320,
        'protein': 6,
        'carbs': 55,
        'fat': 10,
        'fiber': 2,
        'sodium': 200,
        'benefits': ['Ngọt ngào', 'Đặc sản Sóc Trăng', 'Lâu bảo quản'],
    },
    'Banh tet': {
        'calories': 360,
        'protein': 11,
        'carbs': 62,
        'fat': 7,
        'fiber': 3,
        'sodium': 550,
        'benefits': ['Truyền thống miền Nam', 'Giàu năng lượng', 'Nhân đậu ngon'],
    },
    'Banh trang nuong': {
        'calories': 200,
        'protein': 6,
        'carbs': 30,
        'fat': 6,
        'fiber': 1,
        'sodium': 500,
        'benefits': ['Giòn rụm', 'Ăn vặt', 'Đa dạng topping'],
    },
    'Bun dau mam tom': {
        'calories': 400,
        'protein': 18,
        'carbs': 45,
        'fat': 16,
        'fiber': 3,
        'sodium': 1200,
        'benefits': ['Đậm đà', 'Giàu protein', 'Độc đáo'],
    },
    'Bun mam': {
        'calories': 380,
        'protein': 20,
        'carbs': 44,
        'fat': 13,
        'fiber': 3,
        'sodium': 1400,
        'benefits': ['Đặc sản miền Tây', 'Nước dùng đậm đà', 'Nhiều hải sản'],
    },
    'Bun rieu': {
        'calories': 340,
        'protein': 16,
        'carbs': 46,
        'fat': 10,
        'fiber': 3,
        'sodium': 1100,
        'benefits': ['Giàu canxi', 'Nước dùng chua ngọt', 'Nhiều rau'],
    },
    'Bun thit nuong': {
        'calories': 420,
        'protein': 22,
        'carbs': 50,
        'fat': 14,
        'fiber': 3,
        'sodium': 900,
        'benefits': ['Thơm ngon', 'Giàu protein', 'Nhiều rau sống'],
    },
    'Ca kho to': {
        'calories': 280,
        'protein': 24,
        'carbs': 12,
        'fat': 15,
        'fiber': 1,
        'sodium': 1000,
        'benefits': ['Giàu omega-3', 'Đậm đà', 'Tốt cho tim mạch'],
    },
    'Canh chua': {
        'calories': 120,
        'protein': 10,
        'carbs': 15,
        'fat': 3,
        'fiber': 2,
        'sodium': 800,
        'benefits': ['Chua ngọt', 'Khai vị', 'Nhiều rau củ'],
    },
    'Chao long': {
        'calories': 220,
        'protein': 14,
        'carbs': 20,
        'fat': 9,
        'fiber': 1,
        'sodium': 900,
        'benefits': ['Bổ dưỡng', 'Ấm bụng', 'Giàu protein'],
    },
    'Mi quang': {
        'calories': 390,
        'protein': 18,
        'carbs': 52,
        'fat': 11,
        'fiber': 3,
        'sodium': 1000,
        'benefits': ['Đặc sản Quảng Nam', 'Đa dạng topping', 'Màu sắc bắt mắt'],
    },
    'Nem chua': {
        'calories': 180,
        'protein': 12,
        'carbs': 8,
        'fat': 11,
        'fiber': 0.5,
        'sodium': 700,
        'benefits': ['Chua ngọt', 'Lên men tự nhiên', 'Giàu probiotic'],
    },
    'Xoi xeo': {
        'calories': 350,
        'protein': 8,
        'carbs': 58,
        'fat': 10,
        'fiber': 2,
        'sodium': 400,
        'benefits': ['Giàu năng lượng', 'Thơm bùi', 'Ăn sáng lý tưởng'],
    },
}

def get_nutrition_info(food_name: str) -> Optional[Dict]:
    """
    Lấy thông tin dinh dưỡng của món ăn từ database
    
    Args:
        food_name: Tên món ăn
        
    Returns:
        Dictionary chứa thông tin dinh dưỡng
    """
    # Chuẩn hóa tên 
    food_name_normalized = food_name.strip()

    # Tìm trong database
    nutrition = NUTRITION_DATABASE.get(food_name_normalized)
    
    if nutrition:
        # Thêm tên vào kết quả
        result = {'name': food_name, **nutrition}
        return result
    
    # Nếu không tìm thấy, trả về thông tin mặc định
    return {
        'name': food_name,
        'calories': None,
        'protein': None,
        'carbs': None,
        'fat': None,
        'fiber': None,
        'benefits': ['Thông tin dinh dưỡng chưa có sẵn'],
        'note': 'Đang cập nhật dữ liệu'
    }


def get_nutrition_with_fallback(food_name: str, api_key: str = None, app_id: str = None) -> Dict:
    """
    Lấy thông tin dinh dưỡng với fallback
    
    Args:
        food_name: Tên món ăn
        api_key: API key (không sử dụng)
        app_id: App ID (không sử dụng)
        
    Returns:
        Dictionary chứa thông tin dinh dưỡng
    """
    return get_nutrition_info(food_name)


def format_nutrition_display(nutrition: Dict) -> str:
    """
    Format thông tin dinh dưỡng thành chuỗi HTML đẹp
    
    Args:
        nutrition: Dictionary chứa thông tin dinh dưỡng
        
    Returns:
        Chuỗi HTML được format
    """
    html = f"<h4>{nutrition['name']}</h4>"
    
    if nutrition.get('calories'):
        html += f"<p><strong>Calories:</strong> {nutrition['calories']} kcal</p>"
    
    if nutrition.get('protein'):
        html += f"<p><strong>Protein:</strong> {nutrition['protein']}g</p>"
    
    if nutrition.get('carbs'):
        html += f"<p><strong>Carbs:</strong> {nutrition['carbs']}g</p>"
    
    if nutrition.get('fat'):
        html += f"<p><strong>Fat:</strong> {nutrition['fat']}g</p>"
    
    if nutrition.get('fiber'):
        html += f"<p><strong>Fiber:</strong> {nutrition['fiber']}g</p>"
    
    if nutrition.get('sodium'):
        html += f"<p><strong>Sodium:</strong> {nutrition['sodium']}mg</p>"
    
    if nutrition.get('benefits'):
        html += "<p><strong>Lợi ích:</strong></p><ul>"
        for benefit in nutrition['benefits']:
            html += f"<li>{benefit}</li>"
        html += "</ul>"
    
    if nutrition.get('note'):
        html += f"<p><em>{nutrition['note']}</em></p>"
    
    return html


def get_healthy_recommendations(food_name: str, top_k: int = 3) -> List[Dict]:
    """
    Hàm đề xuất các món ăn lành mạnh hơn thay thế cho món ăn gốc.
    Tiêu chí: Ít chất béo hơn, calo không vượt quá nhiều, 
    và cấu trúc dinh dưỡng (Protein, Carbs) gần với món gốc nhất.
    
    Args:
        food_name: Tên món ăn gốc vừa được nhận diện
        top_k: Số lượng món ăn muốn đề xuất (Mặc định lấy top 3)
    Returns:
        Danh sách các dictionary chứa thông tin món ăn được đề xuất kèm chỉ số tối ưu
    """
    # Lấy thông tin dinh dưỡng của món ăn gốc
    source_nutrition = get_nutrition_info(food_name)
    
    # Nếu món ăn gốc không tồn tại hoặc chưa có dữ liệu dinh dưỡng
    if not source_nutrition or source_nutrition.get('calories') is None:
        return []

    s_calories = source_nutrition['calories']
    s_fat = source_nutrition['fat']
    s_protein = source_nutrition['protein']
    s_carbs = source_nutrition['carbs']

    recommendations = []

    for name, data in NUTRITION_DATABASE.items():
        # Điều kiện 1: Không tự đề xuất chính nó
        if name.lower() == food_name.lower():
            continue
        
        # Điều kiện 2 (Lọc thô): 
        # - Phải ít dầu mỡ (chất béo) hơn món gốc: data['fat'] < s_fat
        # - Lượng Calo tương đương hoặc thấp hơn (cho phép sai số tối đa +50 kcal để không bỏ sót các món giàu đạm)
        if data['fat'] < s_fat and data['calories'] <= (s_calories + 50):
            
            # Tính khoảng cách Euclidean giữa Protein và Carbs 
            # Khoảng cách càng nhỏ chứng tỏ cấu trúc bữa ăn càng tương đồng về độ no và năng lượng hoạt động
            distance = math.sqrt((data['protein'] - s_protein)**2 + (data['carbs'] - s_carbs)**2)
            
            # Tính toán các chỉ số cắt giảm để hiển thị lên UI
            fat_reduced = s_fat - data['fat']
            calories_saved = s_calories - data['calories']
            
            rec_item = {
                'name': name,
                **data,
                'distance': distance,          # Dùng để sắp xếp
                'fat_reduced': fat_reduced,    # Lượng chất béo giảm được
                'calories_saved': calories_saved # Lượng calo cắt giảm được
            }
            recommendations.append(rec_item)

    # Sắp xếp danh sách đề xuất: Khoảng cách (distance) càng NHỎ càng đứng TRƯỚC
    recommendations.sort(key=lambda x: x['distance'])

    # Trả về top_k kết quả tối ưu nhất
    return recommendations[:top_k]


def format_recommendations_display(recs: List[Dict], source_name: str) -> str:
    """
    Format danh sách các món ăn đề xuất thành chuỗi HTML để render ra giao diện Frontend.
    """
    if not recs:
        return "<p style='color: #6c757d;'>Hiện chưa có món ăn thay thế phù hợp đạt tiêu chí lành mạnh hơn trong hệ thống.</p>"
        
    html = f"<h4 style='color: #28a745; margin-top: 20px;'>Gợi ý giải pháp thay thế lành mạnh cho món '{source_name}':</h4>"
    html += "<div class='recommendation-list' style='display: flex; gap: 15px; flex-wrap: wrap; margin-top: 10px;'>"
    
    for item in recs:
        # Chuẩn bị chuỗi text hiển thị lượng calo tăng/giảm
        if item['calories_saved'] > 0:
            cal_text = f"<span style='color: #28a745;'>Giảm {item['calories_saved']} kcal</span>"
        elif item['calories_saved'] < 0:
            cal_text = f"<span style='color: #dc3545;'>Tăng {abs(item['calories_saved'])} kcal</span>"
        else:
            cal_text = "Calo tương đương"

        html += f"""
        <div class='rec-card' style='border: 1px solid #ced4da; border-left: 5px solid #28a745; padding: 15px; border-radius: 6px; background-color: #f8fff9; min-width: 260px; flex: 1;'>
            <h5 style='margin: 0 0 10px 0; color: #155724; font-size: 16px;'>{item['name']}</h5>
            <p style='margin: 4px 0;'><strong>Calories:</strong> {item['calories']} kcal ({cal_text})</p>
            <p style='margin: 4px 0;'><strong>Chất béo:</strong> {item['fat']}g <span style='color: #28a745;'>(Ít hơn {item['fat_reduced']}g dầu mỡ)</span></p>
            <p style='margin: 4px 0; font-size: 13px; color: #6c757d;'>Đạm (Protein): {item['protein']}g | Tinh bột (Carbs): {item['carbs']}g</p>
            <p style='margin: 8px 0 4px 0;'><strong>Điểm cộng sức khỏe:</strong></p>
            <ul style='margin: 0; padding-left: 20px; font-size: 13px;'>
        """
        for benefit in item['benefits']:
            html += f"<li>{benefit}</li>"
        html += "</ul></div>"
        
    html += "</div>"
    return html