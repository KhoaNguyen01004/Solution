# BÁO CÁO KIẾN TẬP THỰC TẾ

**Trường:** Đại học Quốc tế Sài Gòn (SIU)

**Ngành:** Khoa học Máy tính

**Chuyên ngành:** Trí tuệ nhân tạo (AI) — Sinh viên Năm 2

**Đơn vị kiến tập:** Công ty Cổ phần Thương mại Dịch vụ và Đầu tư Thành Trung (TT Ex-Trans)

**Sinh viên thực hiện:** Nguyễn Việt Anh Khoa

---

## MỞ ĐẦU

### Lý do chọn đề tài

Ngành Logistics và Vận tải đường bộ giữ vai trò trung tâm trong chuỗi cung ứng hàng hóa nội địa và quốc tế. Công ty Cổ phần Thương mại Dịch vụ và Đầu tư Thành Trung (thương hiệu vận tải TT Ex-Trans) là một đơn vị vận tải tại khu vực phía Nam với quy mô vận hành hơn 110 xe tải thùng kín và 36 xe container. Với khối lượng dữ liệu hành trình và tiêu hao nhiên liệu phát sinh hàng ngày, doanh nghiệp đang đối mặt với bài toán số hóa quy trình quản lý đội xe, giám sát nhiên liệu và tối ưu hóa lộ trình di chuyển. Đợt kiến tập là cơ sở để sinh viên chuyên ngành Trí tuệ nhân tạo (AI) áp dụng các thuật toán khoa học máy tính vào giải quyết các bài toán thực tế trong lĩnh vực vận tải.

### Mục đích kiến tập

Mục đích của đợt kiến tập là khảo sát quy trình vận hành nghiệp vụ logistics tại Thành Trung Corp, nhận diện các điểm nghẽn (bottlenecks) trong luồng dữ liệu vận hành, và ứng dụng kiến thức lập trình cùng Trí tuệ nhân tạo đã được trang bị ở năm 2 để xây dựng một giải pháp phần mềm có tính khả thi. Mục tiêu cụ thể là xây dựng một hệ thống quản lý đội xe có khả năng tự động hóa quy trình giám sát, phát hiện bất thường và hỗ trợ ra quyết định cho bộ phận Điều độ.

Đối tượng khảo sát là quy trình điều vận xe tải và xe container tại Công ty Thành Trung, bao gồm dữ liệu hành trình và dữ liệu tiêu hao nhiên liệu của đội xe. Phạm vi khảo sát giới hạn trong việc phân tích luồng thông tin vận hành từ khâu tiếp nhận booking đến khi kết thúc chuyến hàng, xác định các vấn đề kỹ thuật về độ trễ và thiếu nhất quán dữ liệu. Phương pháp thực hiện bao gồm khảo sát thực tế quy trình nghiệp vụ, phỏng vấn nhân sự các phòng ban, phân tích dữ liệu vận hành hiện có, và phát triển phần mềm thử nghiệm theo mô hình iterative. Những nội dung này sẽ được trình bày chi tiết trong các chương tiếp theo.

---

## CHƯƠNG 1: GIỚI THIỆU TỔNG QUAN VỀ CƠ SỞ LÝ THUYẾT VÀ CHỦ ĐỀ KIẾN TẬP

Chương này trình bày các cơ sở lý thuyết chính được sử dụng trong quá trình thực hiện đề tài, bao gồm các thuật toán tối ưu hóa lộ trình, định vị địa lý, phát hiện bất thường và kỹ nghệ dữ liệu.

### 1.1. Tổng quan cơ sở lý thuyết

#### 1.1.1. Bài toán Tối ưu hóa lộ trình (Vehicle Routing Problem — VRP)

Bài toán VRP là một bài toán kinh điển trong lĩnh vực Tối ưu hóa tổ hợp và Khoa học máy tính. VRP yêu cầu tìm kiếm tập hợp các lộ trình tối ưu cho một đội phương tiện nhằm phục vụ một tập hợp các điểm đến với các ràng buộc về thời gian, tải trọng và chi phí. Trong vận tải hàng hóa thực tế, bài toán trở nên phức tạp hơn với các ràng buộc động như giờ cấm tải, cấm đường tại các đô thị lớn (TP. Hồ Chí Minh, Bình Dương, Đồng Nai), trọng tải cho phép theo từng loại xe, và thời gian giao nhận hàng theo khung giờ yêu cầu của khách hàng. Tại Thành Trung Corp, bài toán này thể hiện qua việc bộ phận Điều độ phải phân bổ hơn 110 phương tiện cho các booking hàng ngày, với các ràng buộc về trọng tải, lịch bảo dưỡng, và thời gian lái xe liên tục tối đa.

#### 1.1.2. Thuật toán hình học không gian áp dụng trong Định vị (Geofencing)

Geofencing là kỹ thuật xác định ranh giới ảo trong không gian địa lý, cho phép hệ thống tự động kích hoạt một sự kiện khi phương tiện đi vào hoặc đi ra khỏi vùng ranh giới đã định nghĩa. Cốt lõi của Geofencing là bài toán **Point-in-Polygon (PIP)**: xác định xem một điểm tọa độ GPS có nằm bên trong một đa giác (polygon) cho trước hay không.

Thuật toán được sử dụng để giải quyết bài toán PIP là **Ray Casting Algorithm** (Crossing Number Algorithm) [4]. Nguyên lý của thuật toán: từ điểm cần kiểm tra, một tia (ray) được phóng theo chiều ngang về phía dương vô cực, sau đó đếm số lần tia này cắt qua các cạnh của đa giác. Nếu số lần cắt là số lẻ, điểm nằm bên trong đa giác; nếu là số chẵn, điểm nằm bên ngoài. Độ phức tạp của thuật toán là O(n) với n là số đỉnh của đa giác.

#### 1.1.3. Học máy thống kê áp dụng trong Phát hiện bất thường (Anomaly Detection)

Phát hiện bất thường (Anomaly Detection) là một nhánh của Học máy không giám sát (Unsupervised Learning) [5]. Trong quản lý nhiên liệu đội xe, bài toán phát hiện bất thường được hiểu là việc xác định các phiếu đổ nhiên liệu có mức tiêu hao bất thường so với lịch sử tiêu thụ của chính phương tiện đó. Một phương pháp phổ biến là sử dụng **Moving Average (trung bình trượt)** để thiết lập đường baseline động cho từng phương tiện, từ đó so sánh giá trị thực tế với baseline và gắn cờ nếu vượt quá một ngưỡng nhất định [5].

#### 1.1.4. Kỹ nghệ dữ liệu (Data Engineering) và Tự động hóa thu thập

Một thách thức khi làm việc với dữ liệu vận tải thực tế là dữ liệu không được chuẩn hóa và phân tán trên nhiều nền tảng. Giải pháp cho vấn đề này là xây dựng một **Data Pipeline** tự động có khả năng trích xuất dữ liệu từ các hệ thống nguồn, chuẩn hóa và lưu trữ vào cơ sở dữ liệu tập trung. Các công cụ tự động hóa trình duyệt (Headless Browser) cho phép giả lập tương tác người dùng để lấy dữ liệu từ các hệ thống không có API công khai [2].

### 1.2. Chủ đề thực tập

Chủ đề của đợt kiến tập là xây dựng hệ thống **"Fleet Fuel Management"** — một ứng dụng quản lý đội xe tích hợp các thuật toán tối ưu lộ trình, hàng rào địa lý (Geofencing), và mô hình giám sát bất thường nhiên liệu theo thời gian thực. Hệ thống được phát triển bởi sinh viên năm 2 dưới sự hướng dẫn của đội ngũ kỹ thuật tại Thành Trung Corp, với mục tiêu giải quyết các điểm yếu trong quy trình quản lý đội xe thủ công hiện tại.

### 1.3. Các kết quả và mục tiêu kỳ vọng

Đợt kiến tập đặt ra các mục tiêu cụ thể:

- **Nắm vững quy trình điều vận thực tế:** Sinh viên nắm bắt toàn bộ chu trình vận hành từ khâu nhận booking, xếp lịch, theo dõi chuyến hàng đến khâu nghiệm thu và quyết toán.
- **Hoàn thiện MVP (Minimum Viable Product):** Sản phẩm phần mềm giải quyết ba bài toán cốt lõi gồm Fuel (nhiên liệu), Maintenance (bảo dưỡng), Tracking (định vị) một cách tự động, giảm thiểu ít nhất **80% thao tác ghi chép thủ công** so với quy trình hiện tại.
- **Xây dựng nền tảng kỹ thuật:** Hệ thống có kiến trúc mở, dễ mở rộng, với mã nguồn được tổ chức rõ ràng và có tài liệu kỹ thuật đi kèm.

Những kiến thức nền tảng này là cơ sở để sinh viên tiếp cận và phân tích các vấn đề thực tế tại đơn vị kiến tập. Thông tin về đơn vị kiến tập được trình bày trong Chương 2.

---

## CHƯƠNG 2: MÔ TẢ CƠ QUAN THỰC TẬP THỰC TẾ

Chương này giới thiệu tổng quan về Công ty Cổ phần Thương mại Dịch vụ và Đầu tư Thành Trung, nơi sinh viên thực hiện đợt kiến tập.

### 2.1. Thông tin cơ quan

Công ty Cổ phần Thương mại Dịch vụ và Đầu tư Thành Trung kinh doanh dưới thương hiệu vận tải **TT Ex-Trans**, hoạt động trong lĩnh vực Logistics và vận tải đường bộ. Công ty có trụ sở chính và nhiều chi nhánh tại các tỉnh trọng điểm kinh tế phía Nam. Cơ sở hạ tầng gồm kho bãi hàng hóa, bãi đỗ xe container, và các trạm bảo dưỡng kỹ thuật nội bộ.

### 2.2. Lịch sử hình thành và phát triển

Khởi đầu là một đơn vị vận tải nội địa quy mô nhỏ, Thành Trung Corp đã phát triển thành đối tác cung ứng Logistics chuỗi cung ứng cho các khách hàng như **QNV, FENV** và nhiều nhà máy sản xuất tại các khu công nghiệp. Chiến lược phát triển của công ty tập trung vào chất lượng dịch vụ, giao hàng đúng giờ và đầu tư vào cơ sở vật chất, công nghệ quản lý.

### 2.3. Cơ cấu tổ chức, nhiệm vụ chức năng của các phòng ban

[Figure 2.1: Organizational Structure of Thanh Trung Corp]

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

Sự hiểu biết về tổ chức và quy mô hoạt động của công ty là cơ sở để phân tích các bài toán thực tế trong Chương 3.

---

## CHƯƠNG 3: BÀI TOÁN THỰC TẾ VÀ KHẢO SÁT NGHIỆP VỤ LOGISTICS CHI TIẾT

Chương này trình bày kết quả khảo sát quy trình điều vận logistics thực tế, các nút thắt được nhận diện và những thách thức về chất lượng dữ liệu hiện tại.

### 3.1. Quy trình điều vận xe tải thùng kín và Container thực tế

[Figure 3.1: BPMN diagram of the daily dispatch workflow]

Công việc đầu tiên được giao là khảo sát và ghi nhận quy trình điều vận xe tải thùng kín và container thực tế tại Thành Trung Corp. Quy trình được tìm hiểu thông qua quan sát trực tiếp bộ phận Điều độ và phỏng vấn nhân sự phòng Kinh doanh, phòng Kỹ thuật — Vật tư.

Quy trình điều vận hàng ngày bắt đầu bằng việc thu thập booking từ các khách hàng. Bộ phận Kinh doanh tổng hợp nhu cầu vận chuyển trong ngày, xác nhận các thông tin về địa điểm nhận hàng, địa điểm giao hàng, loại hàng hóa, khối lượng, và yêu cầu đặc biệt. Thời điểm chốt Bảng tổng hợp booking (Consolidated Booking Sheet) chính thức là **15h00** hàng ngày [8]. Việc lên lịch bắt đầu từ **10h00** khi các booking bắt đầu được tiếp nhận, và kéo dài đến 15h00 để tập hợp đầy đủ thông tin. Sau thời điểm này, bộ phận Điều độ phân bổ phương tiện dựa trên tải trọng phù hợp, vị trí hiện tại của xe, lịch bảo dưỡng định kỳ, và thời gian lái xe liên tục tối đa theo quy định.

Công ty áp dụng quy trình an ninh hàng hóa với yêu cầu tài xế chụp **8 tấm hình bắt buộc** cho mỗi chuyến hàng [8]: **4 tấm tại kho xuất hàng** (toàn cảnh xe trước khi xếp hàng, biên bản giao nhận, hình ảnh seal container/thùng xe trước khi khởi hành, hình ảnh xác nhận chủng loại và số lượng hàng) và **4 tấm tại kho đích** (hình ảnh seal còn nguyên vẹn trước khi mở, hình ảnh seal đã mở, biên bản giao nhận có chữ ký bên nhận, toàn cảnh xe sau khi dỡ hàng). 8 tấm hình đóng vai trò là cơ sở dữ liệu xác thực giao nhận, là bằng chứng pháp lý nếu xảy ra tranh chấp về khối lượng, chất lượng hàng hóa hoặc tình trạng niêm phong.

Quy định vận hành yêu cầu tài xế không tự ý gọi điện trực tiếp cho khách hàng hoặc nhân viên Ops hiện trường [8]. Toàn bộ luồng thông tin giao nhận và xử lý sự cố được dẫn dắt qua bộ phận Điều độ nhằm duy trì một nguồn thông tin thống nhất (single source of truth). Bất kỳ sự chậm trễ nào vượt quá **30 phút** so với khung giờ giao hàng cam kết đều phải được lập **Biên bản sự cố** (Incident Report) có đóng dấu xác nhận của công ty [8].

### 3.2. Nhận diện nút thắt (Bottlenecks)

Sau khi khảo sát quy trình và hệ thống công nghệ hiện có, ba bottleneck mang tính hệ thống được nhận diện:

**Bottleneck 1 — Data Latency và Data Inconsistency:** Dữ liệu 8 tấm hình và biên bản giao nhận được cập nhật thủ công qua Zalo và Excel [8]. Tài xế chụp hình và gửi lên nhóm Zalo; nhân viên Điều độ tải ảnh về, kiểm tra, rồi nhập thông tin vào Excel. Khoảng thời gian từ khi chụp hình đến khi cập nhật có thể lên đến hàng giờ hoặc hàng ngày. Zalo và Excel không đồng bộ, dẫn đến thất lạc thông tin. Dữ liệu phi cấu trúc (ảnh, text) không thể phân tích tự động.

**Bottleneck 2 — Thiếu thông tin thời gian thực:** Hệ thống định vị hiện tại **TTAS** (Vietnamese GPS Tracking Platform) cung cấp dữ liệu GPS thô qua giao diện WebForms ASP.NET nhưng không có API công khai hay cơ chế xuất dữ liệu tự động để tích hợp với các hệ thống bên thứ ba [2]. Bộ phận Điều độ không có khả năng nắm bắt vị trí thời gian thực của xe; việc theo dõi hành trình dựa vào các cuộc gọi điện thoại không thường xuyên. Điều này dẫn đến không thể chủ động phát hiện xe chậm trễ, không thể tối ưu hóa lộ trình động, và thông tin vị trí không được lưu vết.

**Bottleneck 3 — Quản lý nhiên liệu và bảo dưỡng thủ công:** Tính toán định mức tiêu hao nhiên liệu và lập kế hoạch bảo dưỡng dựa trên Excel. Nhân viên nhập tay số liệu, tính thủ công, phán đoán dấu hiệu gian lận dựa trên cảm tính. Hệ thống không có cảnh báo tự động khi xe sắp đến hạn thay nhớt.

Ba bottleneck này tạo thành một hệ thống quản lý thụ động (reactive), nơi các vấn đề chỉ được phát hiện sau khi đã xảy ra. Mục tiêu của giải pháp phần mềm là chuyển đổi mô hình này sang dạng chủ động (proactive).

### 3.3. Phân tích chất lượng dữ liệu hiện tại

Quá trình khảo sát dữ liệu vận hành thực tế cho thấy nhiều thách thức về chất lượng dữ liệu cần được xem xét trước khi xây dựng giải pháp.

Dữ liệu GPS từ TTAS chứa nhiễu (noise) — tọa độ bị drift ngay cả khi xe đang dừng, tọa độ nhảy cóc do mất tín hiệu vệ tinh khi xe đi qua hầm hoặc khu vực đô thị dày đặc nhà cao tầng. Đây là thách thức lớn khi áp dụng các thuật toán geofencing vì tọa độ nhiễu có thể gây phát hiện sai (false positive) khi xe chưa thực sự đến trạm.

Dữ liệu GPS được trả về với trường `speed_status` chứa giá trị tiếng Việt: "Chạy ... km/h", "Dừng ..." kết hợp với trạng thái động cơ (`ad3="Nổ"` hoặc `ad3≠"Nổ"`) để phân biệt trạng thái dừng máy và nổ máy. Việc chuẩn hóa các giá trị này đòi hỏi xử lý chuỗi linh hoạt.

Dữ liệu nhiên liệu từ các phiếu đổ của tài xế cũng có vấn đề về tính đầy đủ. Không phải lúc nào tài xế cũng nhập đầy đủ số KM cũ và KM mới, dẫn đến các phiếu đổ không có KM (no-KM entries) không thể tính được mức tiêu hao L/100km.

Những phân tích về bottleneck và chất lượng dữ liệu trên là cơ sở để đề xuất và xây dựng giải pháp phần mềm được trình bày trong Chương 4.

---

## CHƯƠNG 4: KẾT QUẢ THỰC TẾ - XÂY DỰNG HỆ THỐNG PHẦN MỀM THÔNG MINH "FLEET FUEL MANAGEMENT"

### 4.1. Mô tả chi tiết giải pháp phần mềm

[Figure 4.1: Fleet Fuel Management system architecture]

Trên cơ sở các bottleneck đã nhận diện, sinh viên đã xây dựng hệ thống Fleet Fuel Management theo kiến trúc ứng dụng web ba lớp [6]. Phần backend được phát triển bằng Python với micro-framework Flask để xây dựng RESTful APIs [6], kết hợp với SQLite3 làm hệ quản trị cơ sở dữ liệu [7]. Phần frontend sử dụng Vanilla JavaScript với Chart.js 4.4.7 cho biểu đồ thời gian [3] và Leaflet Map cho bản đồ tương tác. Một luồng daemon hoạt động nền với chu kỳ 60 giây thực hiện đồng bộ dữ liệu GPS, kiểm tra geofence, và cập nhật cache lộ trình.

#### 4.1.1. Xác thực và đồng bộ dữ liệu với TTAS

Hệ thống TTAS là nền tảng WebForms (ASP.NET) không có API công khai — đây là bottleneck kỹ thuật đầu tiên cần giải quyết. Sinh viên đã xây dựng cơ chế tự động hóa sử dụng thư viện **Playwright** để mô phỏng trình duyệt Chromium headless [2]. Playwright thực hiện đăng nhập vào TTAS, trích xuất cookie phiên, và duy trì xác thực cho các lần gọi dữ liệu tiếp theo. Cơ chế này cho phép hệ thống tự động cập nhật dữ liệu GPS và số Odometer định kỳ mà không cần can thiệp thủ công, giải quyết bottleneck về data latency và thiếu thông tin thời gian thực [2].

#### 4.1.2. Cơ chế Geofencing và tự động chuyển phase

Để giải quyết bài toán theo dõi trạng thái xe ra/vào trạm, sinh viên đã ứng dụng thuật toán **Ray Casting** [4] để xác định phương tiện có nằm trong vùng geofence hay không. Thuật toán có độ phức tạp tuyến tính theo số đỉnh của đa giác, phù hợp với yêu cầu xử lý theo chu kỳ 60 giây. Các vùng địa lý của kho bãi được lưu trữ dưới dạng multi-polygon, cho phép mô tả các khu vực có hình dạng phức tạp.

[Figure 4.2: Geofencing zone editor interface]

Cơ chế tự động chuyển phase (Phase Progression) hoạt động dựa trên việc ánh xạ phase hiện tại của chuyến hàng đến tọa độ mục tiêu tương ứng (pickup, waypoint, hoặc destination). Khi background thread phát hiện phương tiện nằm trong vùng geofence của target hiện tại, hệ thống chuyển phase kế tiếp hoặc đánh dấu chuyến hoàn thành. Kết quả là hệ thống có thể tự động phát hiện xe ra/vào kho bãi mà không cần tài xế báo cáo, giảm thiểu thao tác thủ công cho bộ phận Điều độ.

Bên cạnh cơ chế tự động, hệ thống cung cấp khả năng can thiệp thủ công qua giao diện: **Advance** (tăng phase), **Complete** (kết thúc chuyến), **Cancel** (hủy chuyến kèm lý do). Các sự kiện geofence được ghi nhận vào cơ sở dữ liệu để phục vụ truy xuất lịch sử.

#### 4.1.3. Tích hợp định tuyến với OpenRouteService

Module Routing được xây dựng để tính toán lộ trình di chuyển tối ưu. Sinh viên đã tích hợp **ORS Directions API** với cấu hình HGV Profile (Heavy Goods Vehicle) — một cấu hình dành cho xe tải hạng nặng, có tính đến các ràng buộc về chiều cao, trọng lượng, giờ cấm tải, và các tuyến đường cấm xe tải [1].

[Figure 4.3: Route calculated by ORS for a container truck]

Khi ORS API không khả dụng, hệ thống tự động sử dụng **công thức Haversine** để tính khoảng cách đường chim bay, đảm bảo hệ thống vẫn cung cấp thông tin khoảng cách ngay cả khi không có dữ liệu lộ trình chi tiết [1]. Module này giúp bộ phận Điều độ có được lộ trình chính xác theo loại phương tiện, tránh các tuyến đường cấm tải và ước tính thời gian di chuyển đáng tin cậy cho từng chuyến hàng.

#### 4.1.4. Mô hình phát hiện bất thường nhiên liệu

Module phát hiện bất thường nhiên liệu là thành phần mang tính AI cốt lõi của hệ thống. Sinh viên đã áp dụng phương pháp **Moving Average** [5] để thiết lập baseline tiêu thụ nhiên liệu động cho từng phương tiện. Baseline được tính là trung bình cộng của 5 phiếu đổ nhiên liệu gần nhất, với giá trị tiêu hao quy đổi về L/100km. Một phiếu đổ bị gắn cờ bất thường khi vượt ngưỡng 1.20 lần baseline.

Ngưỡng 1.20 được xác định dựa trên phân tích dữ liệu lịch sử của đội xe, cân bằng giữa độ nhạy phát hiện gian lận và tránh cảnh báo giả do biến động nhiên liệu tự nhiên (tắc đường, cao tốc vs nội đô) [5]. Trường hợp phương tiện chưa có đủ 5 phiếu lịch sử, hệ thống cho phép nhập giá trị baseline tĩnh. Các phiếu đổ không có KM được gắn nhãn riêng và loại trừ khỏi tính toán thống kê.

Kết quả được hiển thị trên biểu đồ thời gian Chart.js với marker màu đỏ cho các bất thường và trên bảng dữ liệu với nền màu hổ phách [3]. Cơ chế này giúp bộ phận Kỹ thuật phát hiện sớm dấu hiệu bất thường mà không cần rà soát từng phiếu đổ thủ công.

#### 4.1.5. Pipeline bảo dưỡng tự động

Pipeline bảo dưỡng sử dụng Playwright để tự động đăng nhập vào TTAS, cào dữ liệu Odometer cho tất cả phương tiện, và tính toán tiến độ bảo dưỡng [2]. Dữ liệu được ghi vào cơ sở dữ liệu với ràng buộc UNIQUE để tránh trùng lặp [7]. Trạng thái bảo dưỡng được phân loại theo ba mức: **safe** (xanh — dưới 70% chu kỳ), **warning** (hổ phách — 70% đến 90%), và **danger** (đỏ — trên 90%), với chu kỳ bảo dưỡng mặc định 5000 km.

[Figure 4.4: Oil change dashboard showing safe/warning/danger status]

Pipeline giảm thiểu hoàn toàn việc nhập liệu thủ công cho bảo dưỡng định kỳ. Trước đây, nhân viên phải tự theo dõi số KM của từng xe trên Excel để ước tính lịch thay nhớt; pipeline tự động giúp loại bỏ công đoạn này, giảm rủi ro bỏ sót lịch bảo dưỡng. Hệ thống cũng hỗ trợ phương pháp đồng bộ HTTP POST-based trực tiếp, nhanh hơn vì không cần khởi tạo trình duyệt [2].

#### 4.1.6. Giao diện và kết quả tổng thể

Hệ thống hoàn thành với 6 trang chức năng chính:

[Figure 4.5: Main dashboard map interface]

[Figure 4.6: Fuel efficiency dashboard with anomaly detection]

| Trang | Route URL | Mô tả |
|---|---|---|
| Dashboard Bản đồ | `/` | Bản đồ Leaflet với marker phương tiện, filter, popup, route display |
| Quản lý chuyến | `/manage-trips` | Tạo chuyến với pickup/destination/waypoints |
| Quản lý vùng địa lý | `/locations` | Editor đa giác geofence |
| Lịch sử chuyến | `/trip-history` | Bảng lịch sử chuyến, edit, delete |
| Bảo dưỡng | `/oil-change` | KPI cards, progress bar, fetch KM tự động [2], export CSV |
| Hiệu suất nhiên liệu | `/fuel-efficiency` | Biểu đồ time-series [3], anomaly markers [5], CRUD modal, CSV export |

Hệ thống đáp ứng mục tiêu giảm thiểu đáng kể thao tác thủ công đã đề ra tại Chương 1: theo dõi vị trí xe tự động, phát hiện bất thường nhiên liệu tự động, và cảnh báo bảo dưỡng qua pipeline tự động.

#### 4.1.7. Tối ưu hiệu năng và hạn chế kỹ thuật

Với quy mô 110+ phương tiện và chu kỳ đồng bộ 60 giây, hệ thống gặp thách thức về hiệu năng truy vấn khi thực hiện các JOIN nhiều bảng. Giải pháp được áp dụng là sử dụng SQL thuần với `sqlite3.row_factory = sqlite3.Row` thay vì ORM, giúp giảm overhead và đạt hiệu năng tối đa [7].

Quá trình xây dựng và vận hành hệ thống cũng bộc lộ một số hạn chế:

- **Giới hạn về kiến trúc xử lý song song:** Flask development server chạy single-thread, background thread daemon gây contention khi cùng truy cập dữ liệu. Hướng mở rộng là chuyển sang Gunicorn với nhiều worker hoặc Redis làm cache layer.
- **Geofence dạng 2D:** Hệ thống chỉ dựa trên 2 tọa độ (lat, lng), không xét độ cao (altitude) [4]. Trong tình huống xe đi qua cầu vượt hoặc hầm chui, tọa độ 2D có thể gây dương tính giả.
- **Phụ thuộc vào TTAS:** Dữ liệu thời gian thực phụ thuộc vào sự ổn định của API TTAS. Khi TTAS gặp sự cố, hệ thống chỉ fallback về dữ liệu cached.

### 4.2. Học hỏi từ nơi thực tập

#### 4.2.1. Nhận thức về khoảng cách giữa lý thuyết và thực tế

Quá trình kiến tập tại Thành Trung Corp cho thấy sự khác biệt rõ rệt giữa dữ liệu lý tưởng trên giảng đường và dữ liệu thực tế tại doanh nghiệp. Dữ liệu GPS thô từ TTAS chứa nhiễu và khuyết thiếu, đòi hỏi các kỹ thuật xử lý ngoại lệ linh hoạt. Sinh viên nhận thức được rằng việc xây dựng một hệ thống phần mềm trong môi trường doanh nghiệp không chỉ đòi hỏi kiến thức thuật toán mà còn cần khả năng phân tích và xử lý các tình huống thực tế không nằm trong giáo trình.

Sinh viên cũng học được bài học về tính cấp thời gian (time-critical) trong điều độ logistics chuyên nghiệp: quyết định điều phối xe phải được đưa ra trong vòng vài phút, không thể chờ đợi phân tích dữ liệu kéo dài. Yêu cầu này ảnh hưởng trực tiếp đến kiến trúc của hệ thống — phải có cơ chế caching (15 giây polling) và background thread (60 giây xử lý) để dữ liệu luôn sẵn sàng.

#### 4.2.2. Kỹ năng chuyên môn

Sinh viên nắm vững quy trình điều vận thực tế (chốt lịch 15h00, quy trình 8 tấm hình, kỷ luật giao tiếp tài xế) [8]. Các kiến thức kỹ thuật được củng cố bao gồm: kỹ thuật xử lý và chuẩn hóa dữ liệu thô từ thiết bị định vị thực tế, kỹ thuật tối ưu SQL thuần thay vì ORM [7], thiết kế RESTful API với Flask [6], tích hợp API bên thứ ba (ORS [1], TTAS), và tự động hóa trình duyệt với Playwright [2].

#### 4.2.3. Tác phong công nghiệp và văn hóa doanh nghiệp

Môi trường logistics của Thành Trung Corp yêu cầu tính kỷ luật trong vận hành. Mỗi chuyến hàng chậm trễ có thể gây ảnh hưởng dây chuyền đến lịch trình sản xuất của khách hàng. Văn hóa doanh nghiệp xoay quanh ba giá trị: kỷ luật — chính xác — đúng giờ. Sinh viên học được cách làm việc trong môi trường có áp lực thời gian cao, phối hợp với nhiều phòng ban khác nhau (Điều độ, Kỹ thuật, Kinh doanh) và tuân thủ quy trình báo cáo, xử lý sự cố chặt chẽ.

### 4.3. Đánh giá mối liên hệ giữa lý thuyết và thực tiễn

#### 4.3.1. Tương quan giữa giảng đường và doanh nghiệp

Các môn học tại SIU có tính ứng dụng trực tiếp vào bài toán thực tế:

- **Cấu trúc dữ liệu & Giải thuật:** Nền tảng cho thuật toán Ray Casting (duyệt danh sách đỉnh O(n)), tính centroid đa giác có trọng số (area-weighted centroid), và thiết kế state machine cho trip lifecycle [4].
- **Cơ sở dữ liệu:** Kiến thức về khóa chính, khóa ngoại, ràng buộc UNIQUE, transaction (ACID) và indexing — ứng dụng trong thiết kế schema SQLite, đặc biệt là cơ chế upsert [7].
- **Nhập môn Trí tuệ nhân tạo:** Kiến thức về Anomaly Detection và Time Series Analysis (Moving Average) được cụ thể hóa thành thuật toán 5-entry moving average với ngưỡng phát hiện 20% [5].

#### 4.3.2. Khoảng cách lý thuyết và thực tiễn

- **Môi trường lý tưởng vs. Môi trường nhiễu:** Trên giảng đường, các thuật toán giả định dữ liệu sạch và điều kiện lý tưởng. Thực tế, dữ liệu GPS từ TTAS bị nhiễu (drift) và khuyết thiếu (missing) do mất vệ tinh, nhiễu tín hiệu, thiết bị đầu cuối lỗi thời. Hệ thống phải xử lý các ngoại lệ này một cách mượt mà (graceful degradation).
- **Xe cấm tải, cấm đường:** Trong lý thuyết VRP, thuật toán tìm đường giả định tất cả các tuyến đường đều khả dụng. Tại TP. Hồ Chí Minh, xe tải hạng nặng bị cấm lưu thông trong khung giờ nhất định (6h–9h sáng, 16h–20h chiều) và trên một số tuyến đường. ORS với HGV Profile giải quyết một phần bài toán này [1], nhưng thực tế còn phức tạp hơn với các quy định địa phương.
- **Dữ liệu khuyết thiếu:** Không phải lúc nào tài xế cũng nhập đầy đủ số KM cũ/KM mới. Phiếu đổ không có KM (no-KM entries) không thể tính L/100km nhưng vẫn được lưu trên nhật ký và không được tính vào baseline hay anomaly detection. Hệ thống xử lý qua logic chỉ include vào stats khi dữ liệu hợp lệ [5].

---

## KẾT LUẬN VÀ KIẾN NGHỊ

### Kết luận

Đợt kiến tập tại Công ty Cổ phần Thương mại Dịch vụ và Đầu tư Thành Trung đã hoàn thành các mục tiêu đề ra: khảo sát quy trình điều vận thực tế, nhận diện ba bottleneck mang tính hệ thống, và xây dựng thành công hệ thống **Fleet Fuel Management**.

Về mặt kỹ thuật, hệ thống giải quyết ba bài toán cốt lõi: (1) **Tracking** với Geofencing sử dụng Ray Casting [4] cho phép tự động phát hiện xe ra/vào trạm; (2) **Phát hiện bất thường nhiên liệu** với mô hình Moving Average baseline và ngưỡng phát hiện 20% [5]; và (3) **Tự động hóa bảo dưỡng** với pipeline Playwright cào dữ liệu Odometer từ TTAS [2]. Hệ thống chuyển đổi quy trình quản lý từ thụ động (reactive, dựa trên điện thoại và Excel) sang chủ động (proactive) với dữ liệu thời gian thực, cảnh báo tự động và phát hiện bất thường sớm.

Về mặt kiến thức, sinh viên đã củng cố kỹ năng xử lý dữ liệu thực tế, thiết kế RESTful API, tích hợp hệ thống legacy qua Playwright, và áp dụng các thuật toán CS/AI vào bài toán logistics. Trên phương diện cá nhân, sinh viên học được tác phong làm việc kỷ luật, phối hợp liên phòng ban và giải quyết vấn đề dưới áp lực thời gian trong môi trường doanh nghiệp thực tế. Hệ thống được thiết kế với kiến trúc mở, sẵn sàng cho các phát triển mở rộng trong tương lai.

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

**PHỤ LỤC**

### Phụ lục A: Cấu trúc cơ sở dữ liệu

#### A.1. Bảng `vehicle_trips` — lưu trữ chuyến hàng

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
| `waypoints` | `TEXT` | JSON array |
| `created_at` | `TIMESTAMP` | Thời điểm tạo |
| `updated_at` | `TIMESTAMP` | Lần chỉnh sửa cuối |
| `completed_at` | `TIMESTAMP` | Thời điểm hoàn thành |
| `canceled_at` | `TIMESTAMP` | Thời điểm hủy |
| `cancel_reason` | `TEXT` | Lý do hủy |

#### A.2. Bảng `geofence_events` — nhật ký sự kiện geofence

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

#### A.3. Bảng `vehicles` — danh mục phương tiện

| Cột | Kiểu dữ liệu | Mô tả |
|---|---|---|
| `id` | `INTEGER PK AUTO` | Khóa chính |
| `plate_number` | `TEXT UNIQUE` | Biển số xe |
| `vehicle_type` | `TEXT` | Loại xe |
| `current_driver` | `TEXT` | Tài xế hiện tại |
| `created_at` | `TIMESTAMP` | Ngày tạo |
| `updated_at` | `TIMESTAMP` | Ngày cập nhật |

#### A.4. Bảng `fuel_log` — nhật ký đổ nhiên liệu

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

#### A.5. Bảng `oil_km_log` — lịch sử KM bảo dưỡng

| Cột | Kiểu dữ liệu | Mô tả |
|---|---|---|
| `id` | `INTEGER PK AUTO` | Khóa chính |
| `license_plate` | `TEXT NOT NULL` | Biển số |
| `log_date` | `TEXT NOT NULL` | Ngày ghi nhận |
| `km` | `INTEGER` | Số KM |
| `fetched_at` | `TIMESTAMP` | Thời điểm cào dữ liệu |
| | `UNIQUE(license_plate, log_date)` | Tránh trùng lặp |

#### A.6. Bảng `fuel_vehicle_profile` — định mức nhiên liệu

| Cột | Kiểu dữ liệu | Mô tả |
|---|---|---|
| `license_plate` | `TEXT PRIMARY KEY` | Biển số xe |
| `normal_l_per_100km` | `REAL` | Định mức tiêu hao chuẩn |
| `updated_at` | `TIMESTAMP` | Thời gian cập nhật |

### Phụ lục B: Danh sách API endpoints

| Method | Endpoint | Mô tả |
|---|---|---|
| `GET` | `/` | Dashboard bản đồ |
| `GET` | `/manage-trips` | Quản lý chuyến |
| `GET` | `/locations` | Quản lý vùng địa lý |
| `GET` | `/trip-history` | Lịch sử chuyến |
| `GET` | `/oil-change` | Bảo dưỡng |
| `GET` | `/fuel-efficiency` | Hiệu suất nhiên liệu |
| `GET` | `/api/vehicles` | Dữ liệu phương tiện thời gian thực |
| `GET` | `/api/route-data` | Dữ liệu lộ trình |
| `POST` | `/api/refresh-routes` | Refresh lộ trình |
| `POST` | `/api/set-destination` | Tạo chuyến mới |
| `POST` | `/api/update-trip` | Cập nhật chuyến |
| `POST` | `/api/advance-trip` | Advance/complete chuyến |
| `POST` | `/api/cancel-trip` | Hủy chuyến |
| `GET` | `/api/known-locations` | Danh sách vùng geofence |
| `POST` | `/api/save-location` | Tạo/cập nhật vùng geofence |
| `POST` | `/api/delete-location` | Xóa vùng geofence |
| `GET` | `/api/geofence-events` | Lịch sử sự kiện geofence |
| `GET` | `/api/geocode` | Tra cứu địa danh |
| `GET` | `/api/fuel-log` | Dữ liệu đổ nhiên liệu |
| `GET` | `/api/fuel-log/summary` | Thống kê nhiên liệu |
| `GET` | `/api/fuel-log/export` | Xuất CSV nhiên liệu |
| `POST` | `/api/fuel-log` | Thêm/sửa/xóa phiếu đổ |
| `GET` | `/api/oil-maintenance` | Dữ liệu bảo dưỡng |
| `POST` | `/api/oil-maintenance/fetch-km` | Kích hoạt pipeline cào dữ liệu |

### Phụ lục C: Cấu hình biến môi trường (`.env`)

| Biến | Yêu cầu | Mô tả |
|---|---|---|
| `ORS_API_KEY` | Bắt buộc | OpenRouteService API key |
| `ORS_BASE_URL` | Bắt buộc | ORS endpoint |
| `TTAS_LOGIN_URL` | Bắt buộc* | TTAS login page |
| `TTAS_TRACKING_PAGE_URL` | Bắt buộc | TTAS tracking page |
| `TTAS_TRACKING_API` | Bắt buộc | TTAS AJAX endpoint |
| `TTAS_USERNAME` | Bắt buộc* | TTAS username |
| `TTAS_PASSWORD` | Bắt buộc* | TTAS password |
| `DB_PATH` | Tùy chọn | SQLite path (mặc định: `routing_system.db`) |
| `DEFAULT_RADIUS_KM` | Tùy chọn | Bán kính geofence mặc định (3 km) |
| `ROUTE_REFRESH_INTERVAL_SECONDS` | Tùy chọn | Chu kỳ refresh (60s) |
| `FLASK_HOST` | Tùy chọn | `0.0.0.0` |
| `FLASK_PORT` | Tùy chọn | `5000` |

*Yêu cầu bởi `main.py` cho Playwright login.

### Phụ lục D: Cấu trúc thư mục mã nguồn

```
D:\ChiTuyen\Solution\
├── .env                              # Biến môi trường
├── app.py                            # Flask backend (~2999 dòng)
├── main.py                           # Playwright scraper (~171 dòng)
├── requirements.txt                  # Python dependencies
├── manual_locations.json             # Dữ liệu vùng geofence
├── log.json                          # Cache dữ liệu TTAS
├── routing_system.db                 # SQLite database
├── static/
│   ├── css/
│   │   └── style.css                 # Dark-theme design system
│   └── js/
│       ├── utils.js                  # Geo utilities
│       ├── map.js                    # Map controller
│       ├── manage-trips.js           # Trip management
│       ├── locations.js              # Geofence editor
│       ├── trip-history.js           # Trip history
│       └── oil-change.js             # Oil change dashboard
└── templates/
    ├── index.html                    # Main dashboard
    ├── manage-trips.html             # Trip creation form
    ├── locations.html                # Geofence editor
    ├── trip-history.html             # Trip history
    └── oil-change.html               # Oil change page
```

---

*Báo cáo hoàn thành vào ngày 12 tháng 07 năm 2026 tại Thành phố Hồ Chí Minh.*

*Sinh viên thực hiện: Nguyễn Việt Anh Khoa — SIU K17 — Chuyên ngành Trí tuệ nhân tạo.*
