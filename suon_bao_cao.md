# BÁO CÁO KIẾN TẬP THỰC TẾ
**Trường:** Đại học Quốc tế Sài Gòn (SIU)
**Ngành:** Khoa học Máy tính
**Chuyên ngành:** Trí tuệ nhân tạo (AI) - Sinh viên Năm 2
**Đơn vị kiến tập:** Công ty Cổ phần Thương mại Dịch vụ và Đầu tư Thành Trung (TT Ex-Trans)
**Sinh viên thực hiện:** Nguyễn Việt Anh Khoa

---

## MỞ ĐẦU
* **Lý do chọn đề tài/đơn vị kiến tập:** Tầm quan trọng của Logistics trong nền kinh tế số và cơ hội ứng dụng các thuật toán Trí tuệ nhân tạo (AI), Khoa học dữ liệu nhằm tối ưu hóa chi phí vận hành cho các doanh nghiệp vận tải quy mô lớn như TT Ex-Trans.
* **Mục đích kiến tập:** Cọ xát thực tế quy trình nghiệp vụ logistics, nhận diện các bài toán "nghẽn cổ chai" về dữ liệu và ứng dụng kiến thức lập trình/AI năm 2 để xây dựng giải pháp số hóa.
* **Đối tượng và phạm vi nghiên cứu:** Quy trình điều vận xe tải, xe container tại Thành Trung Corp và dữ liệu hành trình, tiêu hao nhiên liệu của đội xe.

---

## CHƯƠNG 1: GIỚI THIỆU TỔNG QUAN VỀ CƠ SỞ LÝ THUYẾT VÀ CHỦ ĐỀ KIẾN TẬP
### 1.1. Tổng quan cơ sở lý thuyết
* **Bài toán Tối ưu hóa lộ trình (Vehicle Routing Problem - VRP):** Nền tảng thuật toán tìm đường tối ưu cho phương tiện vận tải hạng nặng.
* **Thuật toán hình học không gian áp dụng trong Định vị (Geofencing):** Thuật toán Ray Casting (Point-in-Polygon) dùng để xác định tự động trạng thái xe ra/vào trạm dựa trên tọa độ GPS.
* **Học máy thống kê áp dụng trong Phát hiện bất thường (Anomaly Detection):** Sử dụng các phương pháp trung bình trượt (Moving Average) và thiết lập baseline hành vi tiêu thụ nhiên liệu để phát hiện gian lận hoặc sự cố kỹ thuật.
* **Kỹ nghệ dữ liệu (Data Engineering) và Tự động hóa thu thập (Scraping):** Cơ chế đồng bộ hóa dữ liệu tự động qua trình giả lập web (Headless Browser) để xây dựng pipeline dữ liệu sạch.

### 1.2. Chủ đề thực tập
* Xây dựng hệ thống **"Fleet Fuel Management"** - Ứng dụng thuật toán tối ưu lộ trình, hàng rào địa lý thông minh và mô hình giám sát bất thường nhiên liệu thời gian thực.

### 1.3. Các kết quả và mục tiêu kỳ vọng
* Làm chủ quy trình điều vận thực tế.
* Hoàn thiện sản phẩm MVP (Minimum Viable Product) giải quyết được bài toán Fuel, Maintenance, Tracking một cách tự động, giảm thiểu 80% thao tác ghi chép thủ công.

---

## CHƯƠNG 2: MÔ TẢ CƠ QUAN THỰC TẬP THỰC TẾ (THÀNH TRUNG CORP)
### 2.1. Thông tin cơ quan
* Tên công ty: Công ty Cổ phần Thương mại Dịch vụ và Đầu tư Thành Trung (Thương hiệu vận tải: TT Ex-Trans).
* Trụ sở và các chi nhánh hoạt động.

### 2.2. Lịch sử hình thành và phát triển
* Quá trình phát triển từ đơn vị vận tải nội địa nhỏ thành đối tác cung ứng Logistics chuỗi cung ứng toàn diện.

### 2.3. Cơ cấu tổ chức, nhiệm vụ chức năng của các phòng ban
* Mô hình Trực tuyến - Chức năng (Line-and-Staff). Phân tích cấu trúc kiềng ba chân điều hành: Phòng Kinh doanh ➔ Phòng Điều độ Vận tải ➔ Phòng Kỹ thuật - Vật tư.
* *(Ghi chú dành cho Agent: Chèn sơ đồ khối mô tả luồng thông tin vận hành)*.

### 2.4. Chức năng, nhiệm vụ, phạm vi ngành nghề hoạt động
* Logistics, vận tải đường bộ chặng dài/ngắn, giao nhận Xuất Nhập Khẩu (XNK).

### 2.5. Quy mô nhân sự và năng lực dịch vụ
* Quy mô: Gần 150 nhân sự chuyên môn hóa cao.
* Năng lực đội xe: Hơn 110 đầu xe tải thùng kín (1-10 tấn), 36 xe container và 60 rơ moóc đáp ứng sản lượng lớn.

---

## CHƯƠNG 3: BÀI TOÁN THỰC TẾ VÀ KHẢO SÁT NGHIỆP VỤ LOGISTICS CHI TIẾT
### 3.1. Quy trình điều vận xe tải thùng kín & Container thực tế
* **Quy trình chốt lịch:** Thu thập booking từ khách hàng lớn (QVN, FENV) từ 10h00 và chốt Bảng tổng hợp booking chính thức lúc 15h00 hàng ngày.
* **Quy tắc An ninh hàng hóa nghiêm ngặt:** Quy trình chụp bắt buộc 8 tấm hình (4 tấm tại kho xuất hàng, 4 tấm tại kho đích để kiểm seal và biên bản) làm cơ sở dữ liệu xác thực giao nhận.
* **Kỷ luật giao tiếp tài xế:** Tuyệt đối cấm tài xế tự ý gọi điện cho khách hàng/Ops hiện trường, mọi luồng thông tin phải qua Bộ phận Điều độ. Quy định xử lý sự cố chậm trễ trên 30 phút phải xuất Biên bản sự cố đóng dấu công ty.

### 3.2. Nhận diện nút thắt (Bottlenecks) dưới lăng kính Khoa học máy tính & AI
* Dữ liệu 8 tấm hình và biên bản được cập nhật thủ công lên Zalo/Excel dẫn đến trễ thông tin (Data latency), không thể phân tích tự động.
* Điều độ không nắm rõ thời gian thực (Real-time) xe đến cảng do việc liên lạc qua điện thoại gián đoạn.
* Việc tính toán định mức nhiên liệu và thời gian bảo dưỡng (thay nhớt) phụ thuộc hoàn toàn vào bảng tính Excel thủ công, dễ bỏ sót lỗi kỹ thuật hoặc mất kiểm soát hao hụt.

---

## CHƯƠNG 4: KẾT QUẢ THỰC TẾ - XÂY DỰNG HỆ THỐNG PHẦN MỀM THÔNG MINH "FLEET FUEL MANAGEMENT"
### 4.1. Mô tả chi tiết giải pháp phần mềm kiến trúc AI/CS
* **Kiến trúc hệ thống:** Backend (Python, Flask, SQLite3 phục vụ truy vấn raw SQL tối ưu tốc độ); Frontend (Vanilla JS, Chart.js 4.4.7, Leaflet Map).
* **Module 1: Tracking & Kỹ nghệ Định vị thông minh (Geofencing)**
    * Tích hợp API của hệ thống GPS TTAS hiện tại (lấy dữ liệu thô vị trí thời gian thực).
    * Áp dụng thuật toán **Ray Casting (Point-in-Polygon)** xử lý hình học không gian, tự động nhận diện phương tiện đi vào/ra vùng bán kính kho bãi (Radius 3km) để chuyển đổi trạng thái chuyến đi tự động (Pickup ➔ Waypoints ➔ Destination) không cần tài xế báo cáo.
* **Module 2: Routing tối ưu bằng thuật toán tìm đường hạng nặng**
    * Tích hợp OpenRouteService (ORS) Directions API cấu hình riêng cho xe tải nặng (HGV Profile), tự động tính toán cung đường ngắn nhất, tránh giờ cấm tải, cấm đường.
* **Module 3: Giám sát & Phát hiện bất thường Nhiên liệu (AI/Data Science core)**
    * Thiết lập Baseline động dựa trên giải thuật đường trung bình trượt 5 phiên gần nhất (5-entry moving average per vehicle).
    * Áp dụng quy tắc ngưỡng thông minh: Tự động gắn cờ cảnh báo màu đỏ (Red markers) trên biểu đồ Chart.js khi lượng tiêu thụ thực tế `L/100km > baseline × 1.20` (vượt ngưỡng 20%).
* **Module 4: Pipeline tự động hóa cào dữ liệu bảo dưỡng (Data Scraping Engine)**
    * Sử dụng thư viện **Playwright** chạy ngầm để giả lập đăng nhập hệ thống nội bộ TTAS, cào tự động số Odometer thực tế của xe định kỳ để đưa vào cơ sở dữ liệu SQLite, tự động cảnh báo mức độ an toàn/nguy hiểm của nhớt theo mốc bảo dưỡng 5000km.

### 4.2. Học hỏi từ nơi thực tập
* **Kỹ năng chuyên môn:** Kinh nghiệm xử lý dữ liệu thô (raw data) từ thiết bị định vị thực tế, các kỹ thuật tối ưu hóa câu lệnh SQL không dùng ORM để tăng hiệu năng ứng dụng.
* **Tác phong công nghiệp & Văn hóa doanh nghiệp:** Học tập tính kỷ luật thép trong môi trường vận tải, hiểu được áp lực thời gian (Time-critical) của điều độ logistics chuyên nghiệp.

### 4.3. Đánh giá mối liên hệ giữa lý thuyết và thực tiễn
* **Sự tương quan giữa giảng đường và doanh nghiệp:** Các môn học cốt lõi tại SIU như *Cấu trúc dữ liệu & Giải thuật*, *Cơ sở dữ liệu* và *Nhập môn Trí tuệ nhân tạo* chính là nền tảng để thiết kế nên thuật toán Ray Casting và mô hình tính toán Baseline phát hiện bất thường nhiên liệu.
* **Khoảng cách thực tế:** Lý thuyết thuật toán thường chạy trên môi trường lý tưởng (đường thẳng, dữ liệu sạch), nhưng thực tế hệ thống phải đối mặt với các biến số nhiễu dữ liệu GPS, xe cấm tải, cấm đường và dữ liệu bị khuyết thiếu từ hệ thống định vị gốc.

---

## KẾT LUẬN VÀ KIẾN NGHỊ
* **Kết luận:** Tóm tắt kết quả xây dựng thành công hệ thống Fleet Fuel Management ứng dụng các thuật toán CS/AI cốt lõi. Nêu bật điểm mạnh về khả năng tự động hóa giám sát dựa trên dữ liệu.
* **Kiến nghị:** Đề xuất Thành Trung Corp tiếp tục mở rộng hệ thống số hóa, tích hợp camera thị giác máy tính (Computer Vision) để tự động quét nhận diện mã seal thùng container từ 8 tấm hình an ninh của tài xế thay vì chỉ lưu trữ trên Zalo.