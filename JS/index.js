let anhHienTai = null;

const API_URL = 'http://localhost:5000';

document.addEventListener('DOMContentLoaded', function() {
    console.log('App đã khởi động');
    
    // Lắng nghe sự kiện chọn file
    document.getElementById('fileInput').addEventListener('change', xuLyChonFile);
    
    // Kiểm tra server
    kiemTraServer();
});

// ===== XỬ LÝ CHỌN FILE =====
function xuLyChonFile(event) {
    const file = event.target.files[0];
    
    if (!file) {
        console.warn('Không có file nào được chọn');
        return;
    }
    
    console.log(`File: ${file.name} (${file.size} bytes)`);
    
    // Đọc và hiển thị ảnh preview
    const reader = new FileReader();
    reader.onload = function(e) {
        anhHienTai = file;
        hienThiPreview(e.target.result);
        console.log('Đã load ảnh thành công');
    };
    reader.onerror = function() {
        console.error('Lỗi khi đọc file');
        alert('Không thể đọc file. Vui lòng thử lại!');
    };
    reader.readAsDataURL(file);
}

// HIỂN THỊ PREVIEW 
function hienThiPreview(srcAnh) {
    document.getElementById('previewImage').src = srcAnh;
    document.getElementById('uploadSection').classList.add('hidden');
    document.getElementById('previewSection').classList.remove('hidden');
}

// PHÂN TÍCH ẢNH
async function analyzeFood() {
    console.log('Bắt đầu phân tích...');
    
    // Kiểm tra dữ liệu
    if (!anhHienTai) {
        console.error('Thiếu ảnh:', { anhHienTai });
        alert('Có lỗi xảy ra. Vui lòng thử lại!');
        return;
    }
    
    const btnPhanTich = document.querySelector('.btn-success');
    const textGoc = btnPhanTich.textContent;
    
    // Đổi trạng thái button
    btnPhanTich.textContent = 'Đang phân tích...';
    btnPhanTich.disabled = true;
    
    try {
        // Chuẩn bị dữ liệu gửi lên
        const formData = new FormData();
        formData.append('image', anhHienTai);
        
        console.log(`Gửi request đến: ${API_URL}/api/predict`);
        
        // Gọi API
        const response = await fetch(`${API_URL}/api/predict`, {
            method: 'POST',
            body: formData
        });
        
        console.log(`Trạng thái response: ${response.status}`);
        
        const data = await response.json();
        console.log('Dữ liệu trả về:', data);
        
        // Xử lý kết quả
        if (data.status === 'success') {
            hienThiKetQua(data);
        } else {
            const thongBaoLoi = data.message || 'Không thể phân tích ảnh';
            console.error('Lỗi từ API:', thongBaoLoi);
            alert(`Lỗi: ${thongBaoLoi}`);
        }
        
    } catch (error) {
        console.error('Lỗi kết nối:', error);
        alert(
            'Không thể kết nối đến server!\n\n' +
            `Chi tiết: ${error.message}\n\n` +
            'Kiểm tra:\n' +
            '1. Flask server đã chạy chưa?\n' +
            '2. Đang mở từ http://localhost:5000?'
        );
    } finally {
        // Khôi phục button
        btnPhanTich.textContent = textGoc;
        btnPhanTich.disabled = false;
    }
}

// HIỂN THỊ KẾT QUẢ (ĐÃ CẬP NHẬT)
function hienThiKetQua(data) {
    console.log('Đang render kết quả...');
    
    // Thêm "recommendations" bóc tách từ dữ liệu API trả về
    const { predictions, model, nutrition, recommendations } = data;
    const srcAnhHienTai = document.getElementById('previewImage').src;
    
    // Truyền thêm biến recommendations vào hàm tạo HTML
    let html = taoHTMLKetQua(srcAnhHienTai, predictions, model, nutrition, recommendations);
    
    // Cập nhật DOM
    document.getElementById('previewSection').innerHTML = html;
}

// TẠO HTML KẾT QUẢ (ĐÃ CẬP NHẬT)
function taoHTMLKetQua(srcAnh, predictions, model, nutrition, recommendations) {
    let html = `
        <div style="text-align: center; margin-bottom: 20px;">
            <img src="${srcAnh}" 
                 style="max-width: 100%; max-height: 400px; object-fit: contain; 
                        border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);" 
                 alt="Ảnh đã chọn" />
        </div>
        
        <div style="padding: 24px; text-align: left;">
            <div style="background: linear-gradient(135deg, #F97316 0%, #EF4444 100%); 
                        padding: 16px; border-radius: 8px; margin-bottom: 20px; color: white;">
                <h3 style="margin: 0;">Kết quả nhận diện món ăn</h3>
                <p style="margin: 8px 0 0 0; opacity: 0.9; font-size: 14px;">
                    Model: ${model} - Nhận diện món ăn Việt Nam
                </p>
            </div>
            
            ${taoDanhSachDuDoan(predictions)}
            
            ${nutrition ? taoThongTinDinhDuong(nutrition) : ''}
            
            ${recommendations ? taoThongTinDeXuat(recommendations) : ''}
            <div style="margin-top: 20px; padding-top: 20px; border-top: 2px solid #E5E7EB;">
                <button class="btn btn-gray" onclick="reset()" 
                        style="width: 100%; padding: 14px; font-size: 16px;">
                    Phân tích món ăn khác
                </button>
            </div>
        </div>
    `;
    
    return html;
}

// TẠO DANH SÁCH DỰ ĐOÁN
function taoDanhSachDuDoan(predictions) {
    return predictions.map((pred, index) => {
        const laTotNhat = index === 0;
        const mauNen = laTotNhat ? '#EFF6FF' : '#F9FAFB';
        const mauVien = laTotNhat ? '#3B82F6' : '#E5E7EB';
        const nhanText = laTotNhat ? 'Kết quả tốt nhất' : 'Khả năng khác';
        
        return `
            <div style="margin-bottom: 12px; padding: 16px; 
                        background: ${mauNen}; 
                        border: 2px solid ${mauVien};
                        border-radius: 8px;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <div style="font-weight: 600; font-size: 18px; color: #111827;">
                            ${index + 1}. ${pred.name}
                        </div>
                        <div style="color: #6B7280; font-size: 14px; margin-top: 4px;">
                            ${nhanText}
                        </div>
                    </div>
                    <div style="text-align: right;">
                        <div style="font-size: 24px; font-weight: bold; color: #059669;">
                            ${pred.confidence.toFixed(1)}%
                        </div>
                        <div style="width: 100px; height: 8px; background: #E5E7EB; 
                                    border-radius: 4px; margin-top: 4px; overflow: hidden;">
                            <div style="width: ${pred.confidence}%; height: 100%; 
                                        background: #059669; border-radius: 4px;"></div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }).join('');
}

// TẠO THÔNG TIN DINH DƯỠNG 
function taoThongTinDinhDuong(nutrition) {
    if (!nutrition || nutrition.calories === null) return '';
    
    // Tạo các ô dinh dưỡng
    const cacO = [];
    
    if (nutrition.calories) {
        cacO.push({ nhan: 'Calories', giaTri: `${nutrition.calories} kcal` });
    }
    if (nutrition.protein) {
        cacO.push({ nhan: 'Protein', giaTri: `${nutrition.protein}g` });
    }
    if (nutrition.carbs) {
        cacO.push({ nhan: 'Carbs', giaTri: `${nutrition.carbs}g` });
    }
    if (nutrition.fat) {
        cacO.push({ nhan: 'Fat', giaTri: `${nutrition.fat}g` });
    }
    if (nutrition.fiber) {
        cacO.push({ nhan: 'Fiber', giaTri: `${nutrition.fiber}g` });
    }
    if (nutrition.sodium) {
        cacO.push({ nhan: 'Sodium', giaTri: `${nutrition.sodium}mg` });
    }
    
    const cacOHTML = cacO.map(o => `
        <div style="background: white; padding: 12px; border-radius: 6px;">
            <div style="color: #6B7280; font-size: 12px;">${o.nhan}</div>
            <div style="font-size: 20px; font-weight: bold; color: #059669;">
                ${o.giaTri}
            </div>
        </div>
    `).join('');

    // Tạo danh sách lợi ích
    const loiIchHTML = nutrition.benefits && nutrition.benefits.length > 0 ? `
        <div style="margin-top: 15px; padding-top: 15px; border-top: 1px solid #D1FAE5;">
            <div style="font-weight: 600; color: #065F46; margin-bottom: 8px;">
                Lợi ích sức khỏe:
            </div>
            <ul style="margin: 0; padding-left: 20px; color: #047857;">
                ${nutrition.benefits.map(b => `<li style="margin-bottom: 5px;">${b}</li>`).join('')}
            </ul>
        </div>
    ` : '';
    
    return `
        <div style="background: #F0FDF4; border: 2px solid #10B981; border-radius: 8px; 
                    padding: 20px; margin-top: 20px;">
            <h4 style="color: #065F46; margin: 0 0 15px 0; font-size: 18px;">
                Thông tin dinh dưỡng - ${nutrition.name}
            </h4>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
                ${cacOHTML}
            </div>
            ${loiIchHTML}
        </div>
    `;
}

// TẠO THÔNG TIN ĐỀ XUẤT THAY THẾ LÀNH MẠNH
function taoThongTinDeXuat(recommendations) {
    if (!recommendations || recommendations.length === 0) return '';
    
    const cacTheDeXuatHTML = recommendations.map(item => {
        let textCaloTietKiem = '';
        if (item.calories_saved > 0) {
            textCaloTietKiem = `<span style="color: #10B981; font-weight: 600;">(Tiết kiệm ${item.calories_saved} kcal)</span>`;
        } else if (item.calories_saved < 0) {
            textCaloTietKiem = `<span style="color: #EF4444; font-weight: 600;">(Tăng ${Math.abs(item.calories_saved)} kcal)</span>`;
        } else {
            textCaloTietKiem = `<span style="color: #6B7280;">(Calo tương đương)</span>`;
        }

        const itemsLoiIch = item.benefits && item.benefits.length > 0 
            ? item.benefits.map(b => `<li style="margin-bottom: 3px;">${b}</li>`).join('')
            : '<li>Đang cập nhật dữ liệu...</li>';

        return `
            <div style="background: white; padding: 16px; border: 1px solid #E5E7EB; 
                        border-left: 5px solid #10B981; border-radius: 8px; 
                        box-shadow: 0 2px 4px rgba(0,0,0,0.02); margin-bottom: 12px;">
                <div style="font-weight: 600; font-size: 16px; color: #111827; margin-bottom: 6px;">
                    Thay thế bằng: ${item.name}
                </div>
                <div style="font-size: 14px; color: #374151; line-height: 1.5;">
                    <p style="margin: 4px 0;"><b>Calories:</b> ${item.calories} kcal ${textCaloTietKiem}</p>
                    <p style="margin: 4px 0;"><b>Chất béo:</b> ${item.fat}g <span style="color: #10B981; font-weight: 600;">(Ít hơn ${item.fat_reduced}g dầu mỡ)</span></p>
                    <p style="margin: 4px 0; font-size: 13px; color: #6B7280;">
                        Đạm (Protein): ${item.protein}g | Tinh bột (Carbs): ${item.carbs}g | Xơ: ${item.fiber}g
                    </p>
                </div>
                <div style="margin-top: 10px; padding-top: 8px; border-top: 1px dashed #E5E7EB;">
                    <div style="font-size: 13px; font-weight: 600; color: #065F46; margin-bottom: 4px;">
                        Điểm cộng sức khỏe:
                    </div>
                    <ul style="margin: 0; padding-left: 20px; font-size: 13px; color: #047857;">
                        ${itemsLoiIch}
                    </ul>
                </div>
            </div>
        `;
    }).join('');

    return `
        <div style="background: #EFF6FF; border: 2px solid #3B82F6; border-radius: 8px; 
                    padding: 20px; margin-top: 20px; background-color: #F0FDF4; border-color: #10B981;">
            <h4 style="color: #065F46; margin: 0 0 15px 0; font-size: 18px;">
                Giải pháp thay thế ít dầu mỡ tốt cho sức khỏe
            </h4>
            <div style="display: flex; flex-direction: column; gap: 4px;">
                ${cacTheDeXuatHTML}
            </div>
        </div>
    `;
}

// RESET VỀ BAN ĐẦU 
function reset() {
    console.log('Đang reset...');
    
    // Xóa dữ liệu
    anhHienTai = null;
    
    // Reset input file
    document.getElementById('fileInput').value = '';
    
    // Reset HTML preview section
    document.getElementById('previewSection').innerHTML = `
        <img id="previewImage" class="image" alt="Preview" />
        <div class="button-row">
            <button class="btn btn-success" onclick="analyzeFood()">Phân tích</button>
            <button class="btn btn-gray" onclick="reset()">Hủy</button>
        </div>
    `;
    
    // Hiện upload section, ẩn preview section
    document.getElementById('uploadSection').classList.remove('hidden');
    document.getElementById('previewSection').classList.add('hidden');
    
    console.log('Reset hoàn tất');
}

function kiemTraServer() {
    fetch(`${API_URL}/api/health`)
        .then(res => res.json())
        .then(data => {
            console.log('Server OK:', data);
        })
        .catch(err => {
            console.error('Không kết nối được server:', err);
            console.warn('Kiểm tra Flask server có đang chạy trên port 5000 không');
        });
}