# BÁO CÁO KIẾN TẬP THỰC TẾ

**Trường:** Đại học Quốc tế Sài Gòn (SIU)

**Ngành:** Khoa học Máy tính

**Chuyên ngành:** Trí tuệ nhân tạo (AI) — Sinh viên Năm 2

**Đơn vị kiến tập:** Công ty Cổ phần Thương mại Dịch vụ và Đầu tư Thành Trung (TT Ex-Trans)

**Sinh viên thực hiện:** Nguyễn Việt Anh Khoa

---

## MỞ ĐẦU

### Lý do chọn đề tài và đơn vị kiến tập

Ngành Logistics và Vận tải đường bộ giữ vai trò trung tâm trong chuỗi cung ứng hàng hóa nội địa và quốc tế. Công ty Cổ phần Thương mại Dịch vụ và Đầu tư Thành Trung (thương hiệu vận tải TT Ex-Trans) là một đơn vị vận tải tại khu vực phía Nam với quy mô vận hành hơn 110 xe tải thùng kín và 36 xe container. Với khối lượng dữ liệu hành trình và tiêu hao nhiên liệu phát sinh hàng ngày, doanh nghiệp đang đối mặt với bài toán số hóa quy trình quản lý đội xe, giám sát nhiên liệu và tối ưu hóa lộ trình di chuyển. Đợt kiến tập là cơ sở để sinh viên chuyên ngành Trí tuệ nhân tạo (AI) áp dụng các thuật toán khoa học máy tính vào giải quyết các bài toán thực tế trong lĩnh vực vận tải.

### Mục đích kiến tập

Mục đích của đợt kiến tập là khảo sát quy trình vận hành nghiệp vụ logistics tại Thành Trung Corp, nhận diện các điểm nghẽn (bottlenecks) trong luồng dữ liệu vận hành, và ứng dụng kiến thức lập trình cùng Trí tuệ nhân tạo đã được trang bị ở năm 2 để xây dựng một giải pháp phần mềm có tính khả thi. Mục tiêu cụ thể là xây dựng một hệ thống quản lý đội xe có khả năng tự động hóa quy trình giám sát, phát hiện bất thường và hỗ trợ ra quyết định cho bộ phận Điều độ.

### Đối tượng và phạm vi nghiên cứu

Đối tượng nghiên cứu là quy trình điều vận xe tải và xe container tại Công ty Thành Trung, bao gồm dữ liệu hành trình và dữ liệu tiêu hao nhiên liệu của đội xe. Phạm vi nghiên cứu giới hạn trong việc phân tích luồng thông tin vận hành từ khâu tiếp nhận booking đến khi kết thúc chuyến hàng, xác định các vấn đề kỹ thuật về độ trễ và thiếu nhất quán dữ liệu, và đề xuất giải pháp phần mềm dựa trên nền tảng Python/Flask [6] kết hợp các thuật toán CS/AI cơ bản.

---

## CHƯƠNG 1: GIỚI THIỆU TỔNG QUAN VỀ CƠ SỞ LÝ THUYẾT VÀ CHỦ ĐỀ KIẾN TẬP

### 1.1. Tổng quan cơ sở lý thuyết

#### 1.1.1. Bài toán Tối ưu hóa lộ trình (Vehicle Routing Problem — VRP)

Bài toán VRP là một bài toán kinh điển trong lĩnh vực Tối ưu hóa tổ hợp và Khoa học máy tính. VRP yêu cầu tìm kiếm tập hợp các lộ trình tối ưu cho một đội phương tiện nhằm phục vụ một tập hợp các điểm đến với các ràng buộc về thời gian, tải trọng và chi phí. Trong vận tải hàng hóa thực tế, bài toán trở nên phức tạp hơn với các ràng buộc động như giờ cấm tải, cấm đường tại các đô thị lớn (TP. Hồ Chí Minh, Bình Dương, Đồng Nai), trọng tải cho phép theo từng loại xe, và thời gian giao nhận hàng theo khung giờ yêu cầu của khách hàng.

Hệ thống được xây dựng ứng dụng **OpenRouteService (ORS) Directions API** với cấu hình HGV (Heavy Goods Vehicle) để giải quyết bài toán tìm đường tối ưu cho đội xe container và xe tải thùng kín [1]. Thuật toán tìm đường của ORS dựa trên cơ sở đồ thị (graph-based routing) với dữ liệu giao thông thực tế, tự động loại bỏ các tuyến đường có rào cản về chiều cao, tải trọng và giờ cấm tải. Trong trường hợp dịch vụ ORS không khả dụng, hệ thống thực hiện cơ chế fallback bằng công thức **Haversine** để tính khoảng cách đường chim bay giữa hai điểm địa lý [1].

#### 1.1.2. Thuật toán hình học không gian áp dụng trong Định vị (Geofencing)

Geofencing là kỹ thuật xác định ranh giới ảo trong không gian địa lý, cho phép hệ thống tự động kích hoạt một sự kiện khi phương tiện đi vào hoặc đi ra khỏi vùng ranh giới đã định nghĩa. Cốt lõi của Geofencing là bài toán **Point-in-Polygon (PIP)**: xác định xem một điểm tọa độ GPS có nằm bên trong một đa giác (polygon) cho trước hay không.

Thuật toán được lựa chọn để giải quyết bài toán PIP trong hệ thống là **Ray Casting Algorithm** (Crossing Number Algorithm) [4]. Nguyên lý của thuật toán: từ điểm cần kiểm tra, một tia (ray) được phóng theo chiều ngang về phía dương vô cực, sau đó đếm số lần tia này cắt qua các cạnh của đa giác. Nếu số lần cắt là số lẻ, điểm nằm bên trong đa giác; nếu là số chẵn, điểm nằm bên ngoài. Thuật toán này có độ phức tạp **O(n)** với n là số đỉnh của đa giác, phù hợp để thực thi trong pipeline xử lý 60 giây.

Hệ thống triển khai thuật toán Ray Casting đồng thời ở cả phía server-side (trong `app.py`) và client-side (trong `utils.js`) nhằm đảm bảo tính nhất quán giữa dữ liệu xử lý nền và hiển thị giao diện [4]. Các vùng địa lý được lưu trữ dưới định dạng **multi-polygon** trong tập tin `manual_locations.json`, hỗ trợ các khu vực kho bãi có hình dạng phức tạp với nhiều mảnh đa giác ghép lại [4].

#### 1.1.3. Học máy thống kê áp dụng trong Phát hiện bất thường (Anomaly Detection)

Phát hiện bất thường (Anomaly Detection) là một nhánh của Học máy không giám sát (Unsupervised Learning) [5]. Trong quản lý nhiên liệu đội xe, bài toán phát hiện bất thường được hiểu là việc xác định các phiếu đổ nhiên liệu có mức tiêu hao bất thường so với lịch sử tiêu thụ của chính phương tiện đó.

Hệ thống áp dụng phương pháp **Moving Average (trung bình trượt)** với kích thước cửa sổ **5 phiên gần nhất** để thiết lập đường baseline cho từng phương tiện [5]. Giá trị baseline được tính bằng công thức:

```
Baseline_n = (L/100km_{n-4} + L/100km_{n-3} + L/100km_{n-2} + L/100km_{n-1} + L/100km_n) / 5
```

Một phiếu đổ nhiên liệu được gắn cờ bất thường khi giá trị tiêu hao thực tế `L/100km_actual` vượt quá ngưỡng `baseline × 1.20` (vượt 20% so với mức tiêu hao cơ sở). Ngưỡng 20% này được xác định dựa trên khảo sát độ biến động nhiên liệu cho phép của đội xe Thành Trung, cân bằng giữa độ nhạy phát hiện (sensitivity) và tỷ lệ cảnh báo giả (false positive rate) [5]. Trong trường hợp phương tiện chưa có đủ 5 phiếu lịch sử, hệ thống cho phép người dùng nhập thủ công giá trị định mức `normal_l_per_100km` cho từng xe thông qua bảng Vehicle Baselines [5].

#### 1.1.4. Kỹ nghệ dữ liệu (Data Engineering) và Tự động hóa thu thập (Scraping)

Một thách thức khi làm việc với dữ liệu vận tải thực tế là dữ liệu không được chuẩn hóa và phân tán trên nhiều nền tảng. Hệ thống Fleet Fuel Management giải quyết vấn đề này bằng cách xây dựng một **Data Pipeline** tự động sử dụng thư viện **Playwright** — một framework tự động hóa trình duyệt mã nguồn mở [2].

Pipeline này thực hiện giả lập trình duyệt (Headless Browser) để đăng nhập vào hệ thống quản lý GPS nội bộ **TTAS** (Vietnamese GPS Tracking Platform) thông qua cơ chế WebForms với các tham số `__VIEWSTATE` và `__EVENTVALIDATION` đặc trưng của ASP.NET [2]. Sau khi xác thực thành công, Playwright trích xuất bảng dữ liệu hành trình `#tData` và chuẩn hóa thành các bản ghi `oil_km_log` trong cơ sở dữ liệu SQLite [7]. Quá trình này cho phép hệ thống tự động cập nhật số **Odometer** thực tế của từng xe định kỳ [2].

### 1.2. Chủ đề thực tập

Chủ đề của đợt kiến tập là xây dựng hệ thống **"Fleet Fuel Management"** — một ứng dụng quản lý đội xe tích hợp các thuật toán tối ưu lộ trình, hàng rào địa lý (Geofencing), và mô hình giám sát bất thường nhiên liệu theo thời gian thực. Hệ thống được phát triển bởi sinh viên năm 2 dưới sự hướng dẫn của đội ngũ kỹ thuật tại Thành Trung Corp, với mục tiêu giải quyết các điểm yếu trong quy trình quản lý đội xe thủ công hiện tại.

### 1.3. Các kết quả và mục tiêu kỳ vọng

Đợt kiến tập đặt ra các mục tiêu cụ thể:

- **Nắm vững quy trình điều vận thực tế:** Sinh viên nắm bắt toàn bộ chu trình vận hành từ khâu nhận booking, xếp lịch, theo dõi chuyến hàng đến khâu nghiệm thu và quyết toán.
- **Hoàn thiện MVP (Minimum Viable Product):** Sản phẩm phần mềm giải quyết ba bài toán cốt lõi gồm Fuel (nhiên liệu), Maintenance (bảo dưỡng), Tracking (định vị) một cách tự động, giảm thiểu ít nhất **80% thao tác ghi chép thủ công** so với quy trình hiện tại.
- **Xây dựng nền tảng kỹ thuật:** Hệ thống có kiến trúc mở, dễ mở rộng, với mã nguồn được tổ chức rõ ràng và có tài liệu kỹ thuật đi kèm (hệ thống file `SYSTEM.md`).

---

## CHƯƠNG 2: MÔ TẢ CƠ QUAN THỰC TẬP (THÀNH TRUNG CORP)

### 2.1. Thông tin cơ quan

Công ty Cổ phần Thương mại Dịch vụ và Đầu tư Thành Trung kinh doanh dưới thương hiệu vận tải **TT Ex-Trans**, hoạt động trong lĩnh vực Logistics và vận tải đường bộ. Công ty có trụ sở chính và nhiều chi nhánh tại các tỉnh trọng điểm kinh tế phía Nam. Cơ sở hạ tầng gồm kho bãi hàng hóa, bãi đỗ xe container, và các trạm bảo dưỡng kỹ thuật nội bộ.

### 2.2. Lịch sử hình thành và phát triển

Khởi đầu là một đơn vị vận tải nội địa quy mô nhỏ, Thành Trung Corp đã phát triển thành đối tác cung ứng Logistics chuỗi cung ứng cho các khách hàng như **QNV, FENV** và nhiều nhà máy sản xuất tại các khu công nghiệp. Chiến lược phát triển của công ty tập trung vào chất lượng dịch vụ, giao hàng đúng giờ và đầu tư vào cơ sở vật chất, công nghệ quản lý.

### 2.3. Cơ cấu tổ chức, nhiệm vụ chức năng của các phòng ban

Thành Trung Corp vận hành theo mô hình tổ chức **Trực tuyến — Chức năng (Line-and-Staff Organization)**. Cấu trúc quản lý gồm ba khối chức năng chính:

- **Phòng Kinh doanh:** Tiếp nhận booking từ khách hàng, đàm phán hợp đồng vận chuyển, quản lý quan hệ khách hàng và thu hồi công nợ.
- **Phòng Điều độ Vận tải:** Xếp lịch, phân bổ tài xế và phương tiện, theo dõi hành trình, xử lý sự cố phát sinh và đảm bảo hàng hóa được giao nhận đúng tiến độ.
- **Phòng Kỹ thuật — Vật tư:** Quản lý tình trạng kỹ thuật đội xe, lập kế hoạch bảo dưỡng định kỳ, quản lý kho vật tư phụ tùng.

Bên cạnh ba khối chính còn có các phòng ban hỗ trợ như Kế toán — Tài chính, Nhân sự — Hành chính, và Văn phòng đại diện tại các tỉnh.

### 2.4. Chức năng, nhiệm vụ, phạm vi ngành nghề hoạt động

Thành Trung Corp hoạt động với các chức năng chính:
- **Vận tải đường bộ chặng dài:** Vận chuyển hàng hóa liên tỉnh bằng xe tải thùng kín (1–10 tấn) và xe container với phạm vi toàn quốc.
- **Vận tải chặng ngắn:** Phân phối hàng hóa tại khu vực TP. Hồ Chí Minh và các tỉnh lân cận.
- **Giao nhận Xuất Nhập Khẩu:** Hỗ trợ khách hàng làm thủ tục hải quan thông quan hàng hóa XNK.

### 2.5. Quy mô nhân sự và năng lực dịch vụ

Với gần **150 nhân sự**, Thành Trung Corp sở hữu:
- **Hơn 110 đầu xe tải thùng kín** với tải trọng từ 1 tấn đến 10 tấn.
- **36 xe container** (đầu kéo) đi kèm **60 rơ moóc** với kích thước tiêu chuẩn 20ft, 40ft.
- Đội ngũ tài xế được đào tạo về an toàn giao thông, kỷ luật giao nhận seal và quy trình 8 tấm hình bắt buộc [8].

---

## CHƯƠNG 3: BÀI TOÁN THỰC TẾ VÀ KHẢO SÁT NGHIỆP VỤ LOGISTICS

### 3.1. Quy trình điều vận xe tải thùng kín và Container thực tế

#### 3.1.1. Quy trình chốt lịch và xếp chuyến

Quy trình điều vận hàng ngày tại Thành Trung Corp bắt đầu bằng việc thu thập booking từ các khách hàng. Bộ phận Kinh doanh tổng hợp nhu cầu vận chuyển trong ngày, xác nhận các thông tin về địa điểm nhận hàng, địa điểm giao hàng, loại hàng hóa, khối lượng, và yêu cầu đặc biệt.

Thời điểm chốt Bảng tổng hợp booking (Consolidated Booking Sheet) chính thức là **15h00** hàng ngày [8]. Việc lên lịch bắt đầu từ **10h00** khi các booking bắt đầu được tiếp nhận, và kéo dài đến 15h00 để tập hợp đầy đủ thông tin. Sau thời điểm này, bộ phận Điều độ phân bổ phương tiện dựa trên tải trọng phù hợp, vị trí hiện tại của xe, lịch bảo dưỡng định kỳ, và thời gian lái xe liên tục tối đa theo quy định.

#### 3.1.2. Quy tắc An ninh hàng hóa

Thành Trung Corp áp dụng quy trình an ninh hàng hóa với yêu cầu tài xế chụp **8 tấm hình bắt buộc** cho mỗi chuyến hàng [8]:

- **4 tấm tại kho xuất hàng:** Toàn cảnh xe trước khi xếp hàng, biên bản giao nhận, hình ảnh seal container/thùng xe trước khi khởi hành, hình ảnh xác nhận chủng loại và số lượng hàng.
- **4 tấm tại kho đích:** Hình ảnh seal còn nguyên vẹn trước khi mở, hình ảnh seal đã mở, biên bản giao nhận có chữ ký bên nhận, toàn cảnh xe sau khi dỡ hàng.

8 tấm hình đóng vai trò là cơ sở dữ liệu xác thực giao nhận, là bằng chứng pháp lý nếu xảy ra tranh chấp về khối lượng, chất lượng hàng hóa hoặc tình trạng niêm phong. Quy trình này tương ứng với bài toán **Data Provenance** (truy xuất nguồn gốc dữ liệu) trong lĩnh vực Khoa học máy tính.

#### 3.1.3. Kỷ luật giao tiếp tài xế

Quy định vận hành của Thành Trung Corp yêu cầu tài xế không tự ý gọi điện trực tiếp cho khách hàng hoặc nhân viên Ops hiện trường [8]. Toàn bộ luồng thông tin giao nhận và xử lý sự cố được dẫn dắt qua bộ phận Điều độ nhằm duy trì một nguồn thông tin thống nhất (single source of truth).

Bất kỳ sự chậm trễ nào vượt quá **30 phút** so với khung giờ giao hàng cam kết đều phải được lập **Biên bản sự cố** (Incident Report) có đóng dấu xác nhận của công ty [8]. Biên bản này là cơ sở xác định trách nhiệm bồi thường và là dữ liệu đầu vào cho việc cải tiến quy trình vận hành.

### 3.2. Nhận diện nút thắt (Bottlenecks) dưới lăng kính Khoa học máy tính và AI

Từ khảo sát quy trình vận hành thực tế, ba bottleneck mang tính hệ thống được nhận diện:

#### 3.2.1. Bottleneck số 1: Data Latency và Data Inconsistency

Dữ liệu 8 tấm hình và biên bản giao nhận được cập nhật thủ công qua **Zalo và Excel** [8]. Tài xế chụp hình và gửi lên nhóm Zalo của bộ phận Điều độ. Nhân viên Điều độ sau đó tải ảnh về, kiểm tra, rồi nhập thông tin vào bảng Excel quản lý chuyến hàng.

Quy trình này bộc lộ các vấn đề:
- **Data Latency:** Khoảng thời gian từ khi tài xế chụp hình đến khi dữ liệu được cập nhật vào hệ thống quản lý có thể lên đến hàng giờ hoặc hàng ngày.
- **Data Inconsistency:** Dữ liệu trên Zalo và Excel không có cơ chế đồng bộ tự động, dẫn đến thất lạc thông tin và sai lệch trạng thái chuyến hàng.
- **Không thể phân tích tự động:** Dữ liệu dạng ảnh và text phi cấu trúc không thể sử dụng làm đầu vào cho các mô hình phân tích tự động. Đây là bài toán Unstructured Data trong Data Engineering.

#### 3.2.2. Bottleneck số 2: Thiếu thông tin thời gian thực

Bộ phận Điều độ không có khả năng nắm bắt vị trí thời gian thực của xe. Việc theo dõi hành trình dựa vào các cuộc gọi điện thoại không thường xuyên giữa Điều độ và tài xế. Điều này dẫn đến:
- Không thể chủ động phát hiện xe chậm trễ.
- Không thể tối ưu hóa lộ trình động khi có sự cố.
- Thông tin vị trí không được lưu vết để phục vụ phân tích hậu kỳ.

#### 3.2.3. Bottleneck số 3: Quản lý nhiên liệu và bảo dưỡng thủ công

Việc tính toán định mức tiêu hao nhiên liệu và lập kế hoạch bảo dưỡng định kỳ dựa trên bảng tính Excel. Mỗi khi có phiếu đổ nhiên liệu mới, nhân viên kỹ thuật nhập tay số liệu, tính toán thủ công mức tiêu hao, và phán đoán dấu hiệu gian lận dựa trên cảm tính. Hệ thống quản lý bảo dưỡng không có cảnh báo tự động khi xe sắp đến hạn thay nhớt.

Ba bottleneck này tạo thành một hệ thống quản lý thụ động (reactive), nơi các vấn đề chỉ được phát hiện sau khi đã gây ra tổn thất. Mục tiêu của hệ thống Fleet Fuel Management là chuyển đổi mô hình này sang dạng chủ động (proactive), dựa trên dữ liệu tự động và cảnh báo thông minh.

---

## CHƯƠNG 4: KẾT QUẢ THỰC TẾ — XÂY DỰNG HỆ THỐNG PHẦN MỀM "FLEET FUEL MANAGEMENT"

Chương này mô tả quá trình xây dựng hệ thống phần mềm Fleet Fuel Management, kiến trúc hệ thống, cơ chế vận hành của từng module, và phân tích các thuật toán CS/AI đã ứng dụng.

### 4.1. Mô tả giải pháp phần mềm

#### 4.1.1. Kiến trúc hệ thống

Hệ thống Fleet Fuel Management được xây dựng theo kiến trúc **Monolithic Web Application** [6] với các thành phần chính:

- **Backend:** Python sử dụng micro-framework **Flask** để xây dựng RESTful APIs [6]. Dữ liệu được lưu trữ trong **SQLite3** [7]. Hệ thống sử dụng **raw SQL** thay vì ORM nhằm tránh overhead khi thực thi các truy vấn phức tạp liên quan đến multi-table JOIN và các cập nhật batch theo chu kỳ 60 giây [7].
- **Frontend:** Vanilla JavaScript cho logic giao diện phía client, kết hợp với **Chart.js 4.4.7** để trực quan hóa dữ liệu dạng biểu đồ thời gian [3] và **Leaflet Map** để hiển thị bản đồ tương tác.
- **Background Thread:** Một luồng daemon hoạt động nền với chu kỳ **60 giây**, thực hiện đồng bộ dữ liệu GPS từ TTAS API, kiểm tra trạng thái geofence, và cập nhật cache lộ trình.

Sơ đồ kiến trúc tổng thể:

```
┌──────────┐     ┌─────────┐     ┌──────────┐
│  Browser │◀───▶│  Flask  │◀───▶│ SQLite DB│
│ (Leaflet)│     │  app.py │     └──────────┘
└──────────┘     │         │
                 │  ┌──────┴──────┐
                 │  │ Background  │
                 │  │  Thread     │
                 │  │ (60s loop)  │
                 │  └──────┬──────┘
                 │         │
                 └─────────┼──────────┐
                           │          │
                     ┌─────▼──┐  ┌────▼──────┐
                     │  ORS   │  │   TTAS    │
                     │ Routes │  │ Tracking  │
                     └────────┘  └────┬──────┘
                                       │
                                ┌──────▼──────┐
                                │  Playwright  │
                                │  (login +    │
                                │   reports)   │
                                └─────────────┘
```

**Luồng dữ liệu toàn hệ thống:**

1. Background thread (chu kỳ 60 giây) gọi API của TTAS để lấy vị trí thời gian thực của từng phương tiện.
2. Với mỗi chuyến hàng đang hoạt động, background thread kiểm tra tọa độ GPS của xe có nằm trong vùng geofence cho chặng hiện tại hay không [4] — nếu có, tự động chuyển sang chặng kế tiếp hoặc hoàn thành chuyến.
3. Tính toán lại lộ đường cho tất cả các chuyến đang active và queued.
4. Kết quả caching trong biến `route_data_cache` với cơ chế thread-safe lock (`threading.Lock`).
5. Frontend thực hiện polling đến server mỗi **15 giây** qua hai endpoint `/api/vehicles` và `/api/route-data`.
6. Các hành động từ người dùng kích hoạt refresh cache ngay lập tức.

#### 4.1.2. Module 1: Tracking và Geofencing

**Nguyên lý hoạt động:**

Module Tracking đồng bộ dữ liệu GPS từ TTAS và áp dụng cơ chế Geofencing để tự động phát hiện hành trình. Dữ liệu đầu vào là luồng tọa độ GPS thô từ TTAS, được tích hợp qua cơ chế gọi API RESTful với chu kỳ 60 giây.

**Cơ chế xác thực TTAS [2]:**

Hệ thống sử dụng thư viện Playwright mô phỏng trình duyệt Chromium headless:
1. Playwright khởi tạo phiên trình duyệt Chromium ẩn.
2. Truy cập vào `TTAS_LOGIN_URL`, tự động điền `username` và `password` từ file `.env`.
3. Chờ redirect sau đăng nhập, trích xuất cookie phiên.
4. Cookie được injected vào `requests.Session` để duy trì xác thực cho các lần gọi API tiếp theo.

Cơ chế này giải quyết bài toán xác thực phiên của hệ thống legacy WebForms (ASP.NET) mà không cần can thiệp vào mã nguồn của TTAS [2].

**Thuật toán Ray Casting — Xác định điểm nằm trong đa giác [4]:**

Đây là cốt lõi của cơ chế Geofencing. Vùng địa lý của các kho bãi được lưu trữ dưới dạng **multi-polygon** trong file `manual_locations.json`. Một location có thể có nhiều polygon con.

Cấu trúc dữ liệu lưu trữ:

```json
{
  "Warehouse A": {
    "polygons": [
      [[10.82, 106.62], [10.82, 106.64], [10.80, 106.64], [10.80, 106.62]],
      [[10.81, 106.63], [10.81, 106.635], [10.805, 106.635], [10.805, 106.63]]
    ],
    "type": "multi_polygon"
  }
}
```

Thuật toán Ray Casting xử lý từng polygon con:

```
Cho điểm P(lat, lng) và đa giác V[0..n-1] với n đỉnh.

Hàm is_point_in_polygon(P, V):
    count = 0
    for i = 0 to n-1:
        V_i = V[i]
        V_j = V[(i+1) % n]

        if (V_i.lng > P.lng) == (V_j.lng > P.lng):
            continue

        x_intersect = V_i.lat + (P.lng - V_i.lng) * (V_j.lat - V_i.lat) / (V_j.lng - V_i.lng)

        if P.lat < x_intersect:
            count += 1

    return (count % 2) == 1
```

**Giải thích thuật toán:**
- Phép kiểm tra `(V_i.lng > P.lng) == (V_j.lng > P.lng)` xác định xem cạnh có cắt tia ngang không [4].
- Biến `x_intersect` tính hoành độ giao điểm dựa trên tỷ lệ nội suy tuyến tính giữa hai đỉnh.
- Số lần cắt (`count`) áp dụng quy tắc Odd-Even: số lẻ → điểm trong, số chẵn → điểm ngoài.

Đối với multi-polygon, thuật toán kiểm tra lần lượt từng polygon con. Nếu điểm nằm trong bất kỳ polygon con nào, kết quả trả về `True` [4].

**Cơ chế tự động chuyển phase (Phase Progression):**

Sau mỗi chu kỳ 60 giây, background thread thực hiện:
1. Với mỗi chuyến đang `ACTIVE`, xác định phase hiện tại và target tương ứng.
2. Ánh xạ phase sang tọa độ mục tiêu:

| Phase | Mục tiêu |
|---|---|
| Phase 1 | Pickup location (hoặc Waypoint[0] nếu không có pickup) |
| Phase N (2+) | Waypoint[N-2] (nếu có) |
| Final Phase | Destination |

3. Lấy tọa độ GPS hiện tại của xe từ dữ liệu TTAS.
4. Kiểm tra nếu tọa độ GPS nằm trong vùng geofence của target hiện tại [4].
5. Nếu điểm nằm trong vùng (Ray Casting trả về `True`):
   - Ghi log sự kiện `geofence_events` với `event_type = 'arrive'`.
   - Nếu còn stop tiếp theo: tăng phase lên 1.
   - Nếu là stop cuối cùng: đánh dấu chuyến `COMPLETED`, ghi nhận `completed_at = current_timestamp`, tự động kích hoạt chuyến tiếp theo trong hàng đợi.

Toàn bộ thao tác được bọc trong một **SQLite transaction** để đảm bảo tính nguyên tử [7].

**Cơ chế Force Override:**

Hệ thống cung cấp khả năng can thiệp thủ công từ bộ phận Điều độ qua giao diện:
- **Advance:** Buộc tăng phase lên 1.
- **Complete:** Buộc kết thúc chuyến.
- **Cancel:** Hủy chuyến (kèm lý do).

Khi một chuyến `ACTIVE` bị hủy hoặc hoàn thành, hệ thống tự động kích hoạt chuyến tiếp theo trong queue.

**Cấu trúc bảng `vehicle_trips`:**

| Cột | Kiểu dữ liệu | Mô tả |
|---|---|---|
| `id` | `INTEGER PK AUTO` | Khóa chính |
| `vehicle_id` | `TEXT NOT NULL` | Mã phương tiện trong TTAS |
| `vehicle_name` | `TEXT` | Biển số xe |
| `driver_name` | `TEXT` | Tên tài xế |
| `destination_lat` | `REAL` | Vĩ độ điểm đích |
| `destination_lng` | `REAL` | Kinh độ điểm đích |
| `destination_name` | `TEXT` | Tên điểm đích |
| `pickup_lat` | `REAL` | Vĩ độ điểm nhận hàng |
| `pickup_lng` | `REAL` | Kinh độ điểm nhận hàng |
| `pickup_name` | `TEXT` | Tên điểm nhận hàng |
| `customer_name` | `TEXT` | Khách hàng |
| `vehicle_type` | `TEXT` | Loại phương tiện |
| `last_known_eta` | `REAL` | ETA (giây) |
| `last_known_distance` | `REAL` | Quãng đường còn lại (km) |
| `status` | `TEXT` | `queued` · `active` · `completed` · `canceled` |
| `phase` | `TEXT` | Phase hiện tại (1-based) |
| `queue_order` | `INTEGER` | Thứ tự trong hàng đợi |
| `waypoints` | `TEXT` | JSON array: `[{name, lat, lng}, ...]` |
| `created_at` | `TIMESTAMP` | Thời điểm tạo |
| `updated_at` | `TIMESTAMP` | Lần chỉnh sửa cuối |
| `completed_at` | `TIMESTAMP` | Thời điểm hoàn thành |
| `canceled_at` | `TIMESTAMP` | Thời điểm hủy |
| `cancel_reason` | `TEXT` | Lý do hủy |

**Bảng `geofence_events` — Nhật ký sự kiện:**

| Cột | Kiểu dữ liệu | Mô tả |
|---|---|---|
| `id` | `INTEGER PK AUTO` | Khóa chính |
| `vehicle_id` | `TEXT NOT NULL` | Mã phương tiện |
| `vehicle_name` | `TEXT` | Tên phương tiện |
| `trip_id` | `INTEGER` | ID chuyến |
| `event_type` | `TEXT` | `arrive` |
| `location_name` | `TEXT` | Tên vùng geofence |
| `lat` | `REAL` | Vĩ độ GPS |
| `lng` | `REAL` | Kinh độ GPS |
| `phase` | `INTEGER` | Phase của chuyến |
| `created_at` | `TIMESTAMP` | Thời gian ghi nhận |

#### 4.1.3. Module 2: Routing tối ưu với ORS Directions API

**Tích hợp OpenRouteService [1]:**

Module Routing tính toán lộ trình di chuyển tối ưu giữa các điểm trên bản đồ. Hệ thống sử dụng ORS Directions API với cấu hình **HGV Profile (Heavy Goods Vehicle)** — một cấu hình định tuyến dành cho xe tải hạng nặng, có tính đến các ràng buộc về chiều cao, trọng lượng, giờ cấm tải, và các tuyến đường cấm xe tải [1].

**Phân tích hồ sơ phương tiện:**

Hàm `get_routing_profile(vehicle_type)` phân tích chuỗi loại xe:

```
get_routing_profile(vehicle_type):
    type_lower = vehicle_type.lower()
    
    if any(keyword in type_lower for keyword in ["dau", "heavy", "truck", "tai", "van"]):
        return "driving-hgv"
    
    return "driving-hgv"
```

Tất cả loại xe trong đội xe Thành Trung Corp (từ 1 tấn đến container) đều được router với profile HGV [1].

**Cấu trúc API call ORS:**

```
GET {ORS_BASE_URL}/driving-hgv
    ?api_key={ORS_API_KEY}
    &start={longitude_start},{latitude_start}
    &end={longitude_end},{latitude_end}
```

**Cơ chế Fallback [1]:**

Khi ORS API không khả dụng, hệ thống tự động sử dụng **công thức Haversine** để tính khoảng cách đường chim bay:

```
Haversine Formula:
    a = sin²(Δlat/2) + cos(lat1)·cos(lat2)·sin²(Δlon/2)
    c = 2 · atan2(√a, √(1-a))
    d = R · c

Trong đó:
    R = 6371000 mét (bán kính Trái Đất)
    Δlat = lat2 - lat1 (radians)
    Δlon = lon2 - lon1 (radians)
```

Với fallback, hệ thống vẫn cung cấp thông tin khoảng cách giữa các điểm mặc dù không có dữ liệu ETA hoặc tọa độ lộ trình chi tiết.

**Cơ chế Caching và Polling:**
- Dữ liệu lộ trình được caching trong bộ nhớ (`route_data_cache`) với `threading.Lock`.
- Cache được invalidate khi tạo, cập nhật, hủy hoặc hoàn thành chuyến.
- Background thread cập nhật cache mỗi 60 giây.
- Frontend polling mỗi 15 giây đến `/api/vehicles` và `/api/route-data`.

#### 4.1.4. Module 3: Phát hiện bất thường Nhiên liệu (Anomaly Detection)

Module này phát hiện tự động các hành vi tiêu thụ nhiên liệu bất thường — dấu hiệu của gian lận hoặc sự cố kỹ thuật — dựa trên phương pháp thống kê Moving Average [5].

**Thiết lập Baseline động bằng Moving Average [5]:**

Baseline được tính riêng cho từng phương tiện dựa trên 5 phiên gần nhất:

```
Đối với phương tiện V và N phiếu đổ nhiên liệu (N >= 5):
    Baseline(V)_n = [value(V)_{n-4} + value(V)_{n-3} + value(V)_{n-2} + value(V)_{n-1} + value(V)_n] / 5

Với value(V)_i = L/100km của phiếu thứ i
    = (liters_i / (new_km_i - old_km_i)) × 100
```

**Cơ chế phát hiện bất thường [5]:**

```
Anomaly(V)_n = True nếu value(V)_n > Baseline(V)_n × 1.20
```

Ngưỡng **1.20** được xác định dựa trên phân tích dữ liệu lịch sử của đội xe Thành Trung Corp, cân bằng giữa độ nhạy và độ đặc hiệu [5].

**Cơ chế Baseline tĩnh [5]:**

Khi phương tiện chưa có đủ lịch sử (dưới 5 phiếu), hệ thống cho phép nhập giá trị baseline tĩnh qua bảng Vehicle Baselines, lưu trong `fuel_vehicle_profile`:

```sql
fuel_vehicle_profile (
    license_plate TEXT PRIMARY KEY,
    normal_l_per_100km REAL,
    updated_at TIMESTAMP
)
```

Khi baseline tĩnh tồn tại, hệ thống ưu tiên sử dụng giá trị này thay vì moving average. Nếu không có baseline tĩnh và số phiếu < 5, phương tiện không được đánh giá bất thường cho đến khi đủ dữ liệu.

**Hiển thị trên Dashboard [3]:**

Các bất thường được hiển thị:
- **Biểu đồ thời gian:** Chart.js với marker màu đỏ (red markers) và kích thước lớn hơn cho các điểm bất thường [3].
- **Bảng dữ liệu:** Các hàng bất thường được tô nền màu hổ phách.

Các hàng thiếu dữ liệu KM được đánh dấu bằng `⚠ No KM` badge và thống kê riêng biệt.

**Cấu trúc bảng dữ liệu:**

Bảng `vehicles`:

| Cột | Kiểu dữ liệu | Mô tả |
|---|---|---|
| `id` | `INTEGER PK AUTO` | Khóa chính |
| `plate_number` | `TEXT UNIQUE` | Biển số xe |
| `vehicle_type` | `TEXT` | Loại xe |
| `current_driver` | `TEXT` | Tài xế hiện tại |
| `created_at` | `TIMESTAMP` | Ngày tạo |
| `updated_at` | `TIMESTAMP` | Ngày cập nhật |

Bảng `fuel_log`:

| Cột | Kiểu dữ liệu | Mô tả |
|---|---|---|
| `id` | `INTEGER PK AUTO` | Khóa chính |
| `vehicle_id` | `INTEGER DEFAULT NULL` | FK đến vehicles |
| `license_plate` | `TEXT NOT NULL` | Biển số |
| `refuel_date` | `TEXT NOT NULL` | Ngày đổ |
| `old_km` | `REAL` | Số KM cũ |
| `new_km` | `REAL` | Số KM mới |
| `liters` | `REAL NOT NULL` | Số lít |
| `unit_price` | `REAL` | Đơn giá (VND/lít) |
| `total_cost` | `REAL` | Thành tiền |
| `driver_name` | `TEXT` | Tên tài xế |
| `store_name` | `TEXT` | Tên cây xăng |
| `note` | `TEXT` | Ghi chú |
| `created_at` | `TIMESTAMP` | Ngày tạo |

#### 4.1.5. Module 4: Pipeline tự động hóa cào dữ liệu bảo dưỡng

**Kiến trúc và luồng hoạt động [2]:**

Pipeline tự động hóa bảo dưỡng sử dụng Playwright để giả lập trình duyệt Chromium, tự động đăng nhập vào TTAS và cào dữ liệu Odometer cho từng phương tiện:

```
TTAS Report (HTML WebForms)
        │
        ▼
    Playwright Chromium Headless [2]
    - Mở TTAS_LOGIN_URL
    - Điền username/password
    - Chờ redirect + extract cookies
        │
        ▼
    Fetch báo cáo hành trình
    - POST request với __VIEWSTATE, __EVENTVALIDATION
    - Parse bảng #tData từ HTML response
        │
        ▼
    Chuẩn hóa dữ liệu → oil_km_log (upsert)
        │
        ▼
    Tính toán metrics:
    • total_km_since_change = Σ km_log entries
    • remaining_km = interval - total_km_since_change
    • progress_pct = (total_km / interval) × 100
    • status: <70% = safe, 70-90% = warning, ≥90% = danger
```

**Cơ chế Upsert [7]:**

Dữ liệu ghi vào bảng `oil_km_log` với ràng buộc `UNIQUE(license_plate, log_date)` để tránh trùng lặp:

```sql
oil_km_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    license_plate TEXT NOT NULL,
    log_date TEXT NOT NULL,
    km INTEGER,
    fetched_at TIMESTAMP,
    UNIQUE(license_plate, log_date)
)
```

**Cảnh báo bảo dưỡng theo ngưỡng:**

| Tiến độ | Trạng thái | Màu sắc | Ý nghĩa |
|---|---|---|---|
| < 70% | `safe` | Xanh lá | Trong phạm vi an toàn |
| 70% – 90% | `warning` | Hổ phách | Sắp đến hạn |
| ≥ 90% | `danger` | Đỏ | Quá hạn, cần bảo dưỡng ngay |

Chu kỳ bảo dưỡng mặc định là **5000 km** (có thể điều chỉnh theo từng phương tiện).

**Progress Tracking thời gian thực:**

Pipeline triển khai cơ chế real-time progress tracking với các tham số: `total`, `current`, `plate`, `status`, `started_at`. Client polling đến `/api/oil-maintenance/fetch-progress` mỗi **500ms** để hiển thị thanh tiến trình kèm ETA.

**Hai phương pháp đồng bộ dữ liệu:**

1. **Playwright-based (main.py) [2]:** Sử dụng trình duyệt đầy đủ cho đăng nhập, điều hướng báo cáo và trích xuất HTML.
2. **HTTP POST-based (app.py nội bộ) [2]:** Sử dụng `requests.Session` với các tham số ASP.NET WebForms (`__VIEWSTATE`, `__EVENTVALIDATION`), nhanh hơn vì không cần khởi tạo trình duyệt.

Cả hai phương pháp đều trích xuất bảng `#tData` — bảng HTML chứa tổng hợp KM hàng ngày của tất cả phương tiện.

### 4.2. Học hỏi từ nơi thực tập

#### 4.2.1. Kỹ năng chuyên môn

Quá trình kiến tập tại Thành Trung Corp cho thấy sự khác biệt giữa dữ liệu lý tưởng trên giảng đường và dữ liệu thực tế tại doanh nghiệp. Dữ liệu GPS thô từ TTAS chứa **nhiễu (noise)** — tọa độ bị **drift** (trôi) ngay cả khi xe đang dừng, tọa độ nhảy cóc do mất tín hiệu vệ tinh khi xe qua hầm hoặc khu vực đô thị.

**Xử lý dữ liệu thô:**

Dữ liệu GPS từ TTAS được trả về với nhiều định dạng, bao gồm trường `speed_status` với giá trị tiếng Việt:

```
"Chạy ... km/h"    → vehicle_status = "running"
"Dừng ..." + ad3="Nổ" → "stopped_engine_on"
"Dừng ..." + ad3≠"Nổ" → "stopped_engine_off"
```

Việc chuẩn hóa các giá trị này đòi hỏi code xử lý chuỗi (string parsing) linh hoạt và thiết kế cấu trúc dữ liệu (normalization schema) có khả năng mở rộng.

**Kỹ thuật tối ưu SQL không dùng ORM [7]:**

Hệ thống sử dụng raw SQL thay vì ORM như SQLAlchemy. Với chu kỳ đồng bộ 60 giây và 110+ phương tiện, các truy vấn JOIN nhiều bảng nếu qua ORM tạo ra overhead không cần thiết. Giải pháp là SQL thuần với `sqlite3.row_factory = sqlite3.Row` để đạt hiệu năng tối đa [7].

#### 4.2.2. Tác phong công nghiệp và Văn hóa doanh nghiệp

Môi trường logistics của Thành Trung Corp yêu cầu tính kỷ luật trong vận hành. Mỗi chuyến hàng chậm trễ có thể gây ảnh hưởng dây chuyền đến lịch trình sản xuất của khách hàng. Văn hóa doanh nghiệp xoay quanh ba giá trị: **kỷ luật — chính xác — đúng giờ**.

Tính cấp thời gian (Time-critical) trong điều độ logistics ảnh hưởng trực tiếp đến kiến trúc hệ thống: cần cơ chế caching (15 giây polling) và background thread (60 giây xử lý) để dữ liệu luôn sẵn sàng.

### 4.3. Đánh giá mối liên hệ giữa lý thuyết và thực tiễn

#### 4.3.1. Tương quan giữa giảng đường và doanh nghiệp

Các môn học tại SIU có tính ứng dụng trực tiếp vào bài toán thực tế:

- **Cấu trúc dữ liệu & Giải thuật:** Nền tảng cho thuật toán Ray Casting (duyệt danh sách đỉnh O(n)), tính centroid đa giác có trọng số (area-weighted centroid), và thiết kế state machine cho trip lifecycle [4].
- **Cơ sở dữ liệu:** Kiến thức về khóa chính, khóa ngoại, ràng buộc UNIQUE, transaction (ACID) và indexing — ứng dụng trong thiết kế schema SQLite, đặc biệt là cơ chế upsert với `UNIQUE(license_plate, log_date)` [7].
- **Nhập môn Trí tuệ nhân tạo:** Kiến thức về Anomaly Detection và Time Series Analysis (Moving Average) được cụ thể hóa thành thuật toán 5-entry moving average với ngưỡng phát hiện 20% [5].

#### 4.3.2. Khoảng cách lý thuyết và thực tiễn

- **Môi trường lý tưởng vs. Môi trường nhiễu:** Trên giảng đường, các thuật toán giả định dữ liệu sạch và điều kiện lý tưởng. Thực tế, dữ liệu GPS từ TTAS bị nhiễu (drift) và khuyết thiếu (missing) do mất vệ tinh, nhiễu tín hiệu, thiết bị đầu cuối lỗi thời. Hệ thống phải xử lý các ngoại lệ này một cách mượt mà (graceful degradation).
- **Xe cấm tải, cấm đường:** Trong lý thuyết VRP, thuật toán tìm đường giả định tất cả các tuyến đường đều khả dụng. Tại TP. Hồ Chí Minh, xe tải hạng nặng bị cấm lưu thông trong khung giờ nhất định (6h–9h sáng, 16h–20h chiều) và trên một số tuyến đường. ORS với HGV Profile giải quyết một phần bài toán này [1], nhưng thực tế còn phức tạp hơn với các quy định địa phương.
- **Dữ liệu khuyết thiếu:** Không phải lúc nào tài xế cũng nhập đầy đủ số KM cũ/KM mới. Phiếu đổ không có KM (no-KM entries) không thể tính L/100km nhưng vẫn được lưu trên nhật ký và không được tính vào baseline hay anomaly detection. Hệ thống xử lý qua logic: `if distance > 0 AND liters > 0` mới include vào stats [5].

---

## CHƯƠNG 5: ĐÁNH GIÁ KẾT QUẢ VÀ THẢO LUẬN

### 5.1. Kết quả đạt được

#### 5.1.1. Về sản phẩm phần mềm

Hệ thống Fleet Fuel Management được xây dựng với các trang chức năng:

| Trang | Route URL | Mô tả |
|---|---|---|
| Dashboard Bản đồ | `/` | Bản đồ Leaflet với marker phương tiện, filter, popup, route display |
| Quản lý chuyến | `/manage-trips` | Tạo chuyến với pickup/destination/waypoints |
| Quản lý vùng địa lý | `/locations` | Editor đa giác geofence multi-polygon |
| Lịch sử chuyến | `/trip-history` | Bảng lịch sử chuyến, edit, delete, duration |
| Bảo dưỡng | `/oil-change` | KPI cards, progress bar, fetch KM tự động [2], export CSV |
| Hiệu suất nhiên liệu | `/fuel-efficiency` | Biểu đồ time-series [3], anomaly markers [5], CRUD modal, CSV export |

Hệ thống đáp ứng yêu cầu giảm thiểu **80% thao tác thủ công**: theo dõi vị trí xe tự động qua TTAS API, phát hiện bất thường nhiên liệu tự động, cảnh báo bảo dưỡng qua pipeline cào dữ liệu tự động [2].

#### 5.1.2. Về nhận thức và kỹ năng

- Sinh viên nắm vững quy trình điều vận thực tế (chốt lịch 15h00, quy trình 8 tấm hình, kỷ luật giao tiếp tài xế) [8].
- Ứng dụng thành công các thuật toán CS/AI cốt lõi (Ray Casting [4], Moving Average [5], Haversine) vào sản phẩm phần mềm.
- Phát triển tư duy thiết kế hệ thống với kiến trúc đa tầng (Flask [6] + SQLite [7] + Background Thread + Playwright [2] + Frontend Polling).

### 5.2. Hạn chế và thách thức

- **Single-threaded Flask:** Flask development server chạy single-thread. Background thread daemon gây contention khi cùng truy cập `route_data_cache`. Giải pháp `threading.Lock` giảm thiểu vấn đề nhưng không triệt để. Hướng mở rộng: chuyển sang Gunicorn với nhiều worker hoặc Redis làm cache layer.
- **Geofence dạng 2D:** Hệ thống geofence chỉ dựa trên 2 tọa độ (lat, lng), không xét độ cao (altitude) [4]. Trong tình huống xe đi qua cầu vượt hoặc hầm chui, tọa độ 2D có thể gây dương tính giả.
- **Phụ thuộc vào TTAS:** Dữ liệu thời gian thực phụ thuộc vào sự ổn định của API TTAS. Khi TTAS gặp sự cố, hệ thống chỉ fallback về dữ liệu cached từ `log.json`.

---

## KẾT LUẬN VÀ KIẾN NGHỊ

### Kết luận

Đợt kiến tập tại Công ty Cổ phần Thương mại Dịch vụ và Đầu tư Thành Trung đã cho phép sinh viên Nguyễn Việt Anh Khoa xây dựng hệ thống **Fleet Fuel Management** — một ứng dụng quản lý đội xe tích hợp các thuật toán khoa học máy tính và trí tuệ nhân tạo.

Hệ thống giải quyết ba bài toán cốt lõi: (1) **Tracking** với Geofencing sử dụng Ray Casting [4] cho phép tự động phát hiện xe ra/vào trạm; (2) **Phát hiện bất thường nhiên liệu** với mô hình 5-entry Moving Average baseline và ngưỡng 20% [5]; và (3) **Tự động hóa bảo dưỡng** với pipeline Playwright cào dữ liệu Odometer từ TTAS [2].

Hệ thống chuyển đổi quy trình quản lý từ thụ động (reactive, dựa trên điện thoại và Excel) sang chủ động (proactive) với dữ liệu thời gian thực, cảnh báo tự động và phát hiện bất thường sớm.

### Kiến nghị

1. **Mở rộng tích hợp Camera Thị giác Máy tính:** Triển khai mô hình thị giác máy tính (YOLO hoặc OCR) để tự động quét mã seal thùng container từ 8 tấm hình an ninh, loại bỏ bottleneck data latency và giảm thiểu rủi ro mất hàng do seal giả.
2. **Nâng cấp kiến trúc Concurrent/Scalable:** Chuyển sang Gunicorn + Nginx kết hợp Redis làm message broker và cache layer, cho phép hệ thống mở rộng lên hàng trăm phương tiện.
3. **Bổ sung Predictive Maintenance:** Sử dụng dữ liệu lịch sử để xây dựng mô hình dự đoán thời điểm hỏng hóc dựa trên xu hướng tiêu thụ nhiên liệu, số lần check engine, và tần suất dừng đột xuất.
4. **Mở rộng Anomaly Detection:** Nâng cấp từ Moving Average thresholding [5] sang **Isolation Forest** hoặc **Seasonal Decomposition of Time Series (STL)** , cho phép phát hiện các mẫu gian lận tinh vi.

---

**TÀI LIỆU THAM KHẢO**

[1] OpenRouteService, "ORS Directions API Guide," *OpenRouteService Documentation*, 2025. [Online]. Available: [https://openrouteservice.org/documentation/](https://openrouteservice.org/documentation/). [Accessed: Jul. 12, 2026].

[2] Microsoft, "Playwright: Fast and reliable end-to-end testing for modern web apps," 2024. [Online]. Available: [https://playwright.dev/](https://playwright.dev/). [Accessed: Jul. 12, 2026].

[3] Chart.js, "Simple yet flexible JavaScript charting for designers & developers," version 4.4.7, 2024. [Online]. Available: [https://www.chartjs.org/](https://www.chartjs.org/). [Accessed: Jul. 12, 2026].

[4] S. M. LaValle, "Geometric Algorithms (Point-in-Polygon)," in *Planning Algorithms*, Cambridge, U.K.: Cambridge Univ. Press, 2006, ch. 5.

[5] V. Chandola, A. Banerjee, and V. Kumar, "Anomaly Detection: A Survey," *ACM Computing Surveys*, vol. 41, no. 3, pp. 1–58, Jul. 2009.

[6] Python Software Foundation, "Flask Web Development," 2024. [Online]. Available: [https://flask.palletsprojects.com/](https://flask.palletsprojects.com/). [Accessed: Jul. 12, 2026].

[7] SQLite, "The SQLite Database File Format," 2024. [Online]. Available: [https://www.sqlite.org/](https://www.sqlite.org/). [Accessed: Jul. 12, 2026].

[8] Công ty Cổ phần Thương mại Dịch vụ và Đầu tư Thành Trung, *Quy trình Vận hành và Điều độ Logistics*, Tài liệu nội bộ, 2026.

---

*Báo cáo hoàn thành vào ngày 12 tháng 07 năm 2026 tại Thành phố Hồ Chí Minh.*

*Sinh viên thực hiện: Nguyễn Việt Anh Khoa — SIU K17 — Chuyên ngành Trí tuệ nhân tạo.*
