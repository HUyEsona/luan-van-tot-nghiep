let anhHienTai = null;
let luongVideoHienTai = null; // Biến lưu luồng camera nhị phân
let mediaRecorder = null;
let recordedChunks = [];
let localStream = null;

const API_URL = 'http://localhost:5000';

document.addEventListener('DOMContentLoaded', function() {
    console.log('App đã khởi động');
    
    // Lắng nghe sự kiện chọn file ảnh cũ
    document.getElementById('fileInput').addEventListener('change', xuLyChonFile);
    
    // Kiểm tra server kết nối
    kiemTraServer();
});

// ===== CHUYỂN ĐỔI PHƯƠNG THỨC ĐẦU VÀO (TABS) =====
function switchMethod(method) {
    console.log(`Chuyển sang chế độ: ${method}`);
    const imageSection = document.getElementById('imageMethodSection');
    const videoSection = document.getElementById('videoMethodSection');
    
    if (method === 'image') {
        imageSection.classList.remove('hidden');
        videoSection.classList.add('hidden');
        tatWebcam();
    } else {
        imageSection.classList.add('hidden');
        videoSection.classList.remove('hidden');
    }
}

// ===== XỬ LÝ CHỌN FILE ẢNH TĨNH =====
function xuLyChonFile(event) {
    const file = event.target.files[0];
    if (!file) {
        console.warn('Không có file nào được chọn');
        return;
    }
    
    console.log(`File ảnh: ${file.name} (${file.size} bytes)`);
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

function hienThiPreview(srcAnh) {
    document.getElementById('previewImage').src = srcAnh;
    document.getElementById('uploadSection').classList.add('hidden');
    document.getElementById('previewSection').classList.remove('hidden');
}

// ===== XỬ LÝ ĐIỀU KHIỂN LIVE WEBCAM CAMERA =====
async function initWebcam() {
    console.log('Đang yêu cầu quyền camera...');
    try {
        localStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
        document.getElementById('webcamView').srcObject = localStream;
        document.getElementById('btnScanCam').disabled = false;
        document.getElementById('btnOpenCam').innerText = "🔄 Camera Sẵn Sàng";
        console.log('Kết nối thành công Live Webcam Stream.');
    } catch (err) {
        console.error('Lỗi truy cập camera:', err);
        alert("Hệ thống không tìm thấy thiết bị thu hình camera hoặc ứng dụng bị từ chối cấp quyền!");
    }
}

function tatWebcam() {
    if (localStream) {
        console.log('Đang tắt luồng camera để giải phóng phần cứng...');
        localStream.getTracks().forEach(track => track.stop());
        document.getElementById('webcamView').srcObject = null;
        document.getElementById('btnScanCam').disabled = true;
        document.getElementById('btnOpenCam').innerText = "Mở Camera";
        localStream = null;
    }
}

// Ghi hình ngắn trong 3 giây để lấy mẫu dữ liệu động chống rung lắc
function captureLiveVideo() {
    if (!localStream) return;
    recordedChunks = [];
    
    try {
        mediaRecorder = new MediaRecorder(localStream, { mimeType: 'video/webm' });
    } catch (e) {
        // Dự phòng cho một số trình duyệt không hỗ trợ định dạng webm mặc định
        mediaRecorder = new MediaRecorder(localStream);
    }
    
    mediaRecorder.ondataavailable = (e) => { 
        if (e.data.size > 0) recordedChunks.push(e.data); 
    };
    
    mediaRecorder.onstop = () => {
        const videoBlob = new Blob(recordedChunks, { type: 'video/webm' });
        console.log(`Đã đóng gói video từ Camera: ${videoBlob.size} bytes`);
        guiVideoSangBackend(videoBlob, "live_stream_capture.webm");
    };

    mediaRecorder.start();
    const btnQuet = document.getElementById('btnScanCam');
    btnQuet.innerText = "⏳ Đang quét món ăn (3s)...";
    btnQuet.disabled = true;

    setTimeout(() => {
        mediaRecorder.stop();
        btnQuet.innerText = "Bắt đầu quét (3s)";
        btnQuet.disabled = false;
    }, 3000);
}

// Xử lý khi user chọn file video có sẵn từ máy tính
function handleVideoUpload(input) {
    if (input.files.length > 0) {
        const file = input.files[0];
        console.log(`Tải file video: ${file.name} (${file.size} bytes)`);
        guiVideoSangBackend(file, file.name);
    }
}

// ===== CALL API DỰ ĐOÁN ẢNH TĨNH =====
async function analyzeFood() {
    console.log('Bắt đầu phân tích ảnh tĩnh...');
    if (!anhHienTai) {
        alert('Có lỗi xảy ra. Vui lòng chọn ảnh trước!');
        return;
    }
    
    const btnPhanTich = document.querySelector('.btn-success');
    const textGoc = btnPhanTich.textContent;
    btnPhanTich.textContent = 'Đang phân tích...';
    btnPhanTich.disabled = true;
    
    try {
        const formData = new FormData();
        formData.append('image', anhHienTai);
        
        const response = await fetch(`${API_URL}/api/predict`, {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        if (data.status === 'success') {
            hienThiKetQua(data);
        } else {
            alert(`Lỗi: ${data.message || 'Không thể phân tích ảnh'}`);
        }
    } catch (error) {
        console.error('Lỗi kết nối:', error);
        alert(`Không thể kết nối đến server: ${error.message}`);
    } finally {
        btnPhanTich.textContent = textGoc;
        btnPhanTich.disabled = false;
    }
}

// ===== CALL API DỰ ĐOÁN CHUỖI VIDEO / CAMERA STREAM =====
async function guiVideoSangBackend(videoBlob, filename) {
    console.log('Đang truyền gói tin video sang API...');
    
    const displaySection = document.getElementById('resultDisplaySection');
    displaySection.classList.remove('hidden');
    document.getElementById('predictionOutput').innerHTML = `
        <div style="padding: 15px; background: #FFFBEB; border: 1px solid #F59E0B; border-radius: 6px; color: #B45309;">
            ⏳ <b>Hệ thống đang bóc tách khung hình video và chạy thuật toán toán học... Vui lòng đợi trong giây lát!</b>
        </div>
    `;
    document.getElementById('nutritionOutput').innerHTML = "";
    document.getElementById('recommendationOutput').innerHTML = "";

    try {
        const formData = new FormData();
        formData.append('video', videoBlob, filename);

        const response = await fetch(`${API_URL}/api/predict-video`, {
            method: 'POST',
            body: formData
        });

        const data = await response.json();
        console.log('Dữ liệu video trả về từ API:', data);

        if (data.status === 'success') {
            // Đổ dữ liệu ra cấu trúc vùng hiển thị kết quả dùng chung của Video Tab
            renderDuLieuVideo(data);
        } else {
            document.getElementById('predictionOutput').innerHTML = `
                <p style="color:red; font-weight:bold;">⚠️ Lỗi cấu trúc: ${data.message || data.error}</p>
            `;
        }
    } catch (error) {
        console.error('Lỗi kết nối API Video:', error);
        document.getElementById('predictionOutput').innerHTML = `
            <p style="color:red; font-weight:bold;">❌ Mất kết nối đến Flask server: ${error.message}</p>
        `;
    }
}

// Render dữ liệu chuyên biệt dành cho khung hiển thị kết quả của Video
function renderDuLieuVideo(data) {
    const { predictions, nutrition, recommendations } = data;
    
    // 1. Hiển thị tên món ăn
    const topPred = predictions[0];
    document.getElementById('predictionOutput').innerHTML = `
        <div style="margin-bottom: 12px; padding: 16px; background: #EFF6FF; border: 2px solid #3B82F6; border-radius: 8px;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <div style="font-weight: 600; font-size: 18px; color: #111827;">1. ${topPred.name}</div>
                    <div style="color: #6B7280; font-size: 14px; margin-top: 4px;">Kết quả phân tích chuỗi hội tụ</div>
                </div>
                <div style="text-align: right;">
                    <div style="font-size: 24px; font-weight: bold; color: #059669;">${topPred.confidence.toFixed(1)}%</div>
                </div>
            </div>
        </div>
    `;

    // 2. Hiển thị thông tin dinh dưỡng gốc (Tự động gọi lại cấu trúc hàm có sẵn của bạn)
    if (nutrition) {
        document.getElementById('nutritionOutput').innerHTML = taoThongTinDinhDuong(nutrition);
    }

    // 3. Hiển thị đề xuất thông minh (Tự động gọi lại cấu trúc hàm có sẵn của bạn)
    if (recommendations) {
        document.getElementById('recommendationOutput').innerHTML = taoThongTinDeXuat(recommendations);
    }
}

// ===== HIỂN THỊ KẾT QUẢ CHO ẢNH TĨNH =====
function hienThiKetQua(data) {
    console.log('Đang kết xuất giao diện ảnh tĩnh...');
    const { predictions, model, nutrition, recommendations } = data;
    const srcAnhHienTai = document.getElementById('previewImage').src;
    
    let html = taoHTMLKetQua(srcAnhHienTai, predictions, model, nutrition, recommendations);
    document.getElementById('previewSection').innerHTML = html;
}

// ===== TẠO CẤU TRÚC HTML KẾT QUẢ CHO ẢNH TĨNH (Giữ nguyên của bạn) =====
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

function taoThongTinDinhDuong(nutrition) {
    if (!nutrition || nutrition.calories === null) return '';
    
    const carbs = parseFloat(nutrition.carbs) || 0;
    const protein = parseFloat(nutrition.protein) || 0;
    const fat = parseFloat(nutrition.fat) || 0;
    const tongMacro = carbs + protein + fat;
    
    let carbsPct = 0, proteinPct = 0, fatPct = 0;
    if (tongMacro > 0) {
        carbsPct = Math.round((carbs / tongMacro) * 100);
        proteinPct = Math.round((protein / tongMacro) * 100);
        fatPct = 100 - carbsPct - proteinPct;
    }
    
    const cacO = [];
    if (nutrition.calories) cacO.push({ nhan: 'Calories', giaTri: `${nutrition.calories} kcal`, mau: '#EF4444' });
    if (nutrition.protein) cacO.push({ nhan: 'Protein', giaTri: `${nutrition.protein}g (${proteinPct}%)`, mau: '#10B981' });
    if (nutrition.carbs) cacO.push({ nhan: 'Carbs', giaTri: `${nutrition.carbs}g (${carbsPct}%)`, mau: '#3B82F6' });
    if (nutrition.fat) cacO.push({ nhan: 'Fat', giaTri: `${nutrition.fat}g (${fatPct}%)`, mau: '#F59E0B' });
    if (nutrition.fiber) cacO.push({ nhan: 'Fiber', giaTri: `${nutrition.fiber}g`, mau: '#4B5563' });
    if (nutrition.sodium) cacO.push({ nhan: 'Sodium', giaTri: `${nutrition.sodium}mg`, mau: '#4B5563' });
    
    const cacOHTML = cacO.map(o => `
        <div style="background: white; padding: 10px; border-radius: 8px; border: 1px solid #E5E7EB;">
            <div style="color: #6B7280; font-size: 11px; font-weight: 500;">${o.nhan}</div>
            <div style="font-size: 15px; font-weight: bold; color: ${o.mau}; margin-top: 2px;">${o.giaTri}</div>
        </div>
    `).join('');
    
    const bieuDoHTML = tongMacro > 0 ? `
        <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; 
                    background: white; padding: 12px; border-radius: 10px; border: 1px solid #E5E7EB; min-width: 120px;">
            <div style="width: 80px; height: 80px; border-radius: 50%;
                        background: conic-gradient(
                            #3B82F6 0% ${carbsPct}%, 
                            #10B981 ${carbsPct}% ${carbsPct + proteinPct}%, 
                            #F59E0B ${carbsPct + proteinPct}% 100%
                        ); display: flex; align-items: center; justify-content: center;">
                <div style="width: 48px; height: 48px; background: white; border-radius: 50%; 
                            display: flex; align-items: center; justify-content: center; 
                            font-size: 11px; font-weight: bold; color: #4B5563; box-shadow: inset 0 2px 4px rgba(0,0,0,0.05);">
                    Tỷ lệ
                </div>
            </div>
            <div style="margin-top: 8px; font-size: 11px; width: 100%; color: #4B5563; font-weight: 500; line-height: 1.4;">
                <div style="display: flex; align-items: center; gap: 4px;"><span style="width: 6px; height: 6px; background: #3B82F6; display: inline-block; border-radius: 50%;"></span> Carbs</div>
                <div style="display: flex; align-items: center; gap: 4px;"><span style="width: 6px; height: 6px; background: #10B981; display: inline-block; border-radius: 50%;"></span> Protein</div>
                <div style="display: flex; align-items: center; gap: 4px;"><span style="width: 6px; height: 6px; background: #F59E0B; display: inline-block; border-radius: 50%;"></span> Fat</div>
            </div>
        </div>
    ` : '';
    
    const loiIchHTML = nutrition.benefits && nutrition.benefits.length > 0 ? `
        <div style="margin-top: 14px; padding-top: 12px; border-top: 1px dashed #10B981;">
            <div style="font-weight: 600; color: #065F46; font-size: 13px; margin-bottom: 4px;">Lợi ích sức khỏe:</div>
            <ul style="margin: 0; padding-left: 18px; color: #047857; font-size: 13px; line-height: 1.5;">
                ${nutrition.benefits.map(b => `<li style="margin-bottom: 3px;">${b}</li>`).join('')}
            </ul>
        </div>
    ` : '';
    
    return `
        <div style="background: #F0FDF4; border: 2px solid #10B981; border-radius: 12px; padding: 16px; margin-top:15px;">
            <h4 style="color: #065F46; margin: 0 0 12px 0; font-size: 16px; font-weight: 600;">
                Chỉ số & Tỷ lệ dinh dưỡng - ${nutrition.name}
            </h4>
            <div style="display: flex; gap: 12px; align-items: stretch;">
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; flex: 1;">
                    ${cacOHTML}
                </div>
                ${bieuDoHTML}
            </div>
            ${loiIchHTML}
        </div>
    `;
}

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
                    <p style="margin: 4px 0;"><b>Chất béo:</b> ${item.fat}g <span style="color: #10B981; font-weight: 600;">(Ít hơn ${item.fat_reduced || 0}g dầu mỡ)</span></p>
                    <p style="margin: 4px 0; font-size: 13px; color: #6B7280;">
                        Đạm (Protein): ${item.protein}g | Tinh bột (Carbs): ${item.carbs}g | Xơ: ${item.fiber || 0}g
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
        <div style="background: #F0FDF4; border: 2px solid #10B981; border-radius: 8px; padding: 20px; margin-top: 20px;">
            <h4 style="color: #065F46; margin: 0 0 15px 0; font-size: 18px;">
                Giải pháp thay thế ít dầu mỡ tốt cho sức khỏe
            </h4>
            <div style="display: flex; flex-direction: column; gap: 4px;">
                ${cacTheDeXuatHTML}
            </div>
        </div>
    `;
}

// ===== RESET TOÀN BỘ TRẠNG THÁI HỆ THỐNG =====
function reset() {
    console.log('Đang thực hiện reset...');
    anhHienTai = null;
    tatWebcam();
    
    // Đặt lại input file ảnh tĩnh
    document.getElementById('fileInput').value = '';
    
    // Đặt lại cấu trúc DOM preview ảnh tĩnh gốc của bạn
    document.getElementById('previewSection').innerHTML = `
        <img id="previewImage" class="image" alt="Preview" />
        <div class="button-row">
            <button class="btn btn-success" onclick="analyzeFood()">Phân tích</button>
            <button class="btn btn-gray" onclick="reset()">Hủy</button>
        </div>
    `;
    
    // Ẩn/Hiện phân vùng về mặc định ban đầu
    document.getElementById('uploadSection').classList.remove('hidden');
    document.getElementById('previewSection').classList.add('hidden');
    document.getElementById('resultDisplaySection').classList.add('hidden');
    
    console.log('Reset hoàn tất.');
}

// ===== KIỂM TRA ĐƯỜNG TRUYỀN SERVER FLASK =====
function kiemTraServer() {
    fetch(`${API_URL}/api/health`)
        .then(res => res.json())
        .then(data => {
            console.log('Kết nối Server AI thành công:', data);
        })
        .catch(err => {
            console.error('Không kết nối được server:', err);
            console.warn('Kiểm tra Flask server có đang chạy trên port 5000 không');
        });
}