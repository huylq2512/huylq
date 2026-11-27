"""Build the VI/EN CV PDFs: python3 build.py (needs google-chrome)."""
import html, subprocess, pathlib

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE.parent

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Merriweather:wght@400;700&family=Source+Sans+3:ital,wght@0,400;0,600;0,700;1,400&display=swap');
@page{size:A4;margin:26px 0 20px}@page :first{margin:0}
*{box-sizing:border-box}
body{margin:0;font-family:'Source Sans 3','Segoe UI',sans-serif;font-size:9.4pt;line-height:1.38;color:#1a1a1a}
.contact{background:#f4f7fb;text-align:center;font-size:8.2pt;padding:7px 0;color:#333;border-bottom:1px solid #e0e6ee}
.contact span{margin:0 12px}
.head{background:#f4f7fb;text-align:center;padding:14px 0 10px;border-bottom:2px solid #1f3a5f}
.head h1{font-family:'Merriweather',serif;font-size:17pt;margin:0;color:#14284a}
.head div{font-size:9pt;font-weight:600;color:#1f3a5f;margin-top:4px}
.page{padding:0 34px}
h2{font-family:'Merriweather',serif;font-size:10.3pt;letter-spacing:.3px;text-transform:uppercase;color:#14284a;border-bottom:1.6px solid #1f3a5f;padding-bottom:3px;margin:16px 0 8px}
.job{margin-bottom:9px}
.row{display:flex;justify-content:space-between;font-weight:700;color:#14284a}
.row .d{font-weight:400;color:#333;font-size:8.6pt}
.co{font-style:italic;color:#555;margin:1px 0 3px}
ul{margin:0;padding-left:15px}
li{margin:1.5px 0}
.role{font-style:italic;font-size:8.4pt;color:#555;margin-bottom:6px}
.proj{margin-bottom:7px;break-inside:avoid-page}
.proj.first{border-left:2.5px solid #c8d2e0;padding-left:12px;margin-left:8px}
.pt{font-weight:700;color:#14284a}
.pt span{font-weight:400;color:#444;font-size:8.6pt}
.edu b{color:#14284a}
"""

def li(items): return "<ul>" + "".join(f"<li>{i}</li>" for i in items) + "</ul>"
def jobs(items):
    return "".join(
        f'<div class="job"><div class="row"><span>{t}</span><span class="d">{d}</span></div>'
        f'<div class="co">{c}</div>{li(b)}</div>' for t, d, c, b in items)
def projs(items):
    out = []
    for n, (t, meta, b) in enumerate(items):
        out.append(f'<div class="proj{" first" if n == 0 else ""}"><div class="pt">{t} <span>· {meta}</span></div>{li(b)}</div>')
    return "".join(out)

VI = dict(
 lang="vi", contact_loc="Ngã Ba Kim - Mù Cang Chải - Lào Cai", title="Software Engineer",
 h_sum="Tóm tắt", h_skill="Kỹ năng", h_exp="Kinh nghiệm làm việc", h_proj="Dự án tiêu biểu", h_edu="Học vấn",
 summary="Lập trình viên Odoo và Python với hơn 4 năm kinh nghiệm phát triển, tùy chỉnh hệ thống ERP trên các phiên bản 15.0–19.0. Có kinh nghiệm xây dựng công cụ tự động hóa bằng Python: xử lý dữ liệu và xuất báo cáo, bot giám sát hệ thống và cảnh báo công việc, chương trình kiểm thử cho các công ty sản xuất. Có kinh nghiệm làm việc với nhiều nghiệp vụ như CRM, Bán hàng, Kế toán, Nhân sự, Kho, Mua hàng và Thương mại điện tử. Bên cạnh chuyên môn lập trình hiện đã và đang đảm nhiệm vai trò Team Lead, phối hợp cùng các thành viên và điều phối công việc để đáp ứng yêu cầu dự án.",
 exp=[
  ("Odoo Development · Team Lead","03/2026 - Hiện tại","Công ty Bắc Hà",[
   "Tham gia dự án AVB về bán hàng, kế toán và dự án Corp về bán hàng B2B, tích hợp Salesforce.",
   "Đảm nhiệm vai trò Team Lead, dẫn dắt nhóm phát triển nhỏ cho hai dự án AVB và Corp.",
   "Xây dựng từ xa chương trình kiểm thử cho khách hàng sản xuất bo mạch điện tử: phân tích Test Specification, cấu hình Test Station và Test Sequence, thực hiện GR&R và xây dựng công cụ tính GR&R, theo dõi CPK/FPY/UPH, xác nhận PVT; viết logic trước khi có thiết bị thật và bàn giao cho IT phía khách hàng triển khai thực tế.",
   "Xây dựng công cụ CLI bằng Python (Pandas, OpenPyXL, Schedule) tự động gom, chuẩn hóa và đối soát số liệu từ 15–20 file, xuất báo cáo Excel; rút thời gian xử lý hằng ngày từ hơn 1 tiếng xuống dưới 30 giây.",
   "Xây dựng bot Python (Cronjob, Redmine, Webhooks, Telegram) giám sát log, dịch vụ và tiến độ công việc, gửi cảnh báo tức thời; giúp phát hiện sự cố sớm hơn 50%."]),
  ("Odoo Development","08/2023 - 03/2026","Công ty Cổ phần Công nghệ Mate JSC",[
   "Phát triển các dự án ERP Tân Phát, E-Contract, Quỹ Trò Nghèo Vùng Cao và E-learning.",
   "Phối hợp BA phân tích nghiệp vụ; tùy chỉnh module, phát triển giao diện OWL, tích hợp API, kiểm thử và hỗ trợ vận hành."]),
  ("Odoo Development","11/2022 - 07/2023","Công ty Cổ phần Công nghệ Viindoo",[
   "Nâng cấp sản phẩm từ Odoo 14 lên 15, tối ưu hiệu năng và điều chỉnh tính năng theo yêu cầu nghiệp vụ.",
   "Tham gia triển khai Staging / Production; cập nhật tài liệu kỹ thuật và lịch sử thay đổi."])],
 role="Vai trò: Python Developer tại các dự án công cụ và tự động hóa; Odoo Development, Team Lead tại Corp và ERP Tân Phát.",
 proj=[
  ("Chương trình kiểm thử bo mạch điện tử (ECB-100)","6 tháng · Python, Excel",[
   "Xây dựng từ xa chương trình kiểm thử cho model bo mạch điện tử (ECB-100) bằng Python, từ Test Specification đến xác nhận PVT; do chưa có thiết bị thật nên viết logic trước, kiểm chứng bằng thiết bị và board mô phỏng, rồi bàn giao cho IT phía khách hàng để triển khai thực tế.",
   "Phân tích Test Specification, xác định 8 Test Item, Test Point và tiêu chuẩn PASS/FAIL (giới hạn LSL/USL, hỗ trợ giới hạn một phía) lưu trong file cấu hình dùng chung.",
   "Xây dựng Test Station: lớp driver cho DMM, bộ đếm tần số, oscilloscope và Test Fixture/Jig (kiểm tra tiếp xúc, mô phỏng sai số kẹp); thiết kế sẵn giao diện để thay bằng thiết bị thật.",
   "Xây dựng Test Sequence với Test Limits và Test Parameters; tự thử lại khi tiếp xúc xấu hoặc thiết bị lỗi, ghi log debug phục vụ Troubleshooting.",
   "Dùng Python và openpyxl xử lý dữ liệu test, phân tích Test Failure bằng Pareto và tự động xuất báo cáo Excel (Summary, Cpk, Pareto, GR&R, dữ liệu gốc).",
   "Xây dựng công cụ tính GR&R (ANOVA, 10 board × 3 người đo × 3 lần đo) để đánh giá độ lặp lại và độ tái lập; phát hiện hạng mục ripple 3V3 ở mức GR&R có điều kiện và đề xuất cải tiến phép đo.",
   "Theo dõi CPK, FPY và UPH theo tiêu chí PVT (FPY ≥ 95%, Cpk ≥ 1.33, UPH ≥ 90); viết unit test cho logic kiểm thử và thống kê."]),
  ("Công cụ tự động xử lý dữ liệu &amp; xuất báo cáo (Internal CLI Tool)","Python Developer · Python, Pandas, OpenPyXL, Regex, Schedule",[
   "Tự động hóa quy trình tổng hợp và đối soát số liệu cuối ngày từ 15–20 file rời rạc (Excel, CSV, JSON) của các bộ phận vận hành, thay thế thao tác lọc và copy-paste thủ công.",
   "Xây dựng công cụ dòng lệnh (CLI) quét và gom dữ liệu đa nguồn; dùng Pandas, Regex để chuẩn hóa ngày tháng, số điện thoại, mã giao dịch, loại bản ghi trùng và tách các dòng dữ liệu lỗi.",
   "Phát triển module đối soát chéo giữa các nguồn để phát hiện sai lệch số liệu và tính các chỉ số tổng hợp theo nhóm.",
   "Dùng OpenPyXL xuất báo cáo theo biểu mẫu chuẩn của công ty, tự động tô màu các dòng bất thường; tích hợp Schedule để chạy định kỳ cuối ngày.",
   "Kết quả: rút ngắn thời gian xử lý báo cáo hằng ngày từ hơn 1 tiếng xuống dưới 30 giây, loại bỏ sai sót do thao tác thủ công."]),
  ("Bot tự động giám sát hệ thống &amp; cảnh báo công việc","Python Developer · Python, Requests, REST API, Webhooks, Telegram API, Linux Cronjob",[
   "Giải quyết việc kiểm tra log lỗi và theo dõi tiến độ công việc của team phân tán trên nhiều nền tảng, tránh phát hiện sự cố chậm.",
   "Phát triển dịch vụ chạy ngầm định kỳ trên server Linux (Cronjob): quét log hệ thống, kiểm tra trạng thái dịch vụ/API nội bộ và thu thập trạng thái công việc từ Redmine.",
   "Xây dựng bộ lọc phân loại mức ưu tiên để nhận diện lỗi bất thường, tiến độ review code đình trệ và đầu việc sắp quá hạn.",
   "Tích hợp Webhooks và Telegram API để đẩy cảnh báo tức thời kèm báo cáo tóm tắt cuối ngày về nhóm chat của team.",
   "Kết quả: đội kỹ thuật phát hiện và xử lý sự cố sớm hơn 50%, tiết kiệm thời gian kiểm tra thủ công mỗi ngày."]),
  ("Corp - Bán hàng B2B và tích hợp Salesforce","Bắc Hà · Team Lead · Nhóm phát triển nhỏ",[
   "Phát triển hệ thống bán hàng B2B trên Odoo, tích hợp Salesforce để đồng bộ dữ liệu khách hàng và hoạt động kinh doanh.",
   "Dẫn dắt nhóm phát triển nhỏ; tùy chỉnh quy trình báo giá, đơn bán và chính sách giá cho khách hàng doanh nghiệp.",
   "Phát triển API tích hợp Odoo – Salesforce, xử lý ánh xạ, đồng bộ dữ liệu và ghi nhận lỗi."]),
  ("ERP Tân Phát","Mate JSC · Team Lead · 11 tháng · 6 thành viên (1 PM, 1 Team Lead, 3 Dev, 1 BA)",[
   "Triển khai ERP cho Công ty Tân Phát (bán hàng, thương mại điện tử): Mua hàng, Bán hàng, Loyalty, Website, CRM.",
   "Nhận yêu cầu từ PM, lập kế hoạch, phân công nhiệm vụ và review giải pháp, mã nguồn."]),
  ("Hợp đồng điện tử E-Contract","Mate JSC · 10 tháng · 9 thành viên (1 PM, 2 BA, 2 QA, 4 Dev)",[
   "Xây dựng giải pháp quản lý và ký số hợp đồng trên Odoo, hỗ trợ PDF, DOCX, XML và ký qua USB Token.",
   "Phát triển OWL Components giao diện kéo-thả để cấu hình vị trí ký; quản lý vòng đời tài liệu đến khi ký xong.",
   "Phát triển Plugin kết nối USB Token, ký số XML bằng chứng thư số; tham gia Code Review."])],
 edu=("Chuyên ngành Công nghệ thông tin","Trường Đại học Mở Hà Nội","03/2024 - Hiện tại"),
 out="LuuQuangHuy_CV_VI.pdf")

EN = dict(
 lang="en", contact_loc="Nga Ba Kim - Mu Cang Chai - Lao Cai", title="Software Engineer",
 h_sum="Summary", h_skill="Skills", h_exp="Work Experience", h_proj="Key Projects", h_edu="Education",
 summary="Odoo and Python developer with over 4 years of experience building and customizing ERP systems on Odoo 15.0–19.0. Built Python tools for data processing and reports, a bot that monitors systems and tasks, and test programs for manufacturing companies. Worked on many business areas: CRM, Sales, Accounting, HR, Inventory, Purchase and E-commerce. Also works as a Team Lead, working with team members and organizing tasks to meet project needs.",
 exp=[
  ("Odoo Development · Team Lead","03/2026 - Present","Bac Ha Company",[
   "Worked on the AVB project (sales and accounting) and the Corp project (B2B sales with Salesforce integration).",
   "Served as Team Lead of a small development team for both AVB and Corp.",
   "Built a test program remotely for a client that makes electronic control boards: read the Test Specification, set up the Test Station and Test Sequence, did GR&amp;R and built a GR&amp;R calculation tool, tracked CPK/FPY/UPH and checked PVT. Wrote the logic first because real equipment was not available, then handed it to the client's IT team to deploy.",
   "Built a Python CLI tool (Pandas, OpenPyXL, Schedule) that collects, cleans and compares data from 15–20 files and exports Excel reports; cut daily work from over 1 hour to under 30 seconds.",
   "Built a Python bot (Cronjob, Redmine, Webhooks, Telegram) that checks logs, services and task progress and sends alerts right away; the team found problems 50% sooner."]),
  ("Odoo Development","08/2023 - 03/2026","Mate Technology JSC",[
   "Developed the Tan Phat ERP, E-Contract, Quy Tro Ngheo Vung Cao (charity fund) and E-learning projects.",
   "Worked with BAs to understand requirements; customized modules, built OWL screens, connected APIs, tested and supported operations."]),
  ("Odoo Development","11/2022 - 07/2023","Viindoo Technology JSC",[
   "Upgraded the product from Odoo 14 to 15, improved performance and changed features to fit business needs.",
   "Helped deploy to Staging / Production; updated technical documents and change logs."])],
 role="Role: Python Developer on tooling and automation projects; Odoo Development, Team Lead on Corp and Tan Phat ERP.",
 proj=[
  ("Electronic Control Board Test Program (ECB-100)","6 months · Python, Excel",[
   "Built a test program remotely for a new electronic control board (ECB-100) in Python, from Test Specification to PVT. No real equipment was available, so I wrote the logic first, tested it with simulated equipment and boards, and handed it to the client's IT team to deploy.",
   "Read the Test Specification and defined 8 Test Items, Test Points and PASS/FAIL limits (LSL/USL, one-sided limits supported) in a shared config file.",
   "Built the Test Station: drivers for DMM, frequency counter, oscilloscope and Test Fixture/Jig (contact check, clamping error); the interfaces can be replaced with real equipment.",
   "Built the Test Sequence with Test Limits and Test Parameters; it retries automatically on bad contact or instrument errors and writes debug logs.",
   "Used Python and openpyxl to process test data, analyze Test Failures with a Pareto chart and create Excel reports (Summary, Cpk, Pareto, GR&amp;R, raw data).",
   "Built a GR&amp;R calculation tool (ANOVA, 10 boards × 3 operators × 3 repeats) to check repeatability and reproducibility; found the 3V3 ripple item at conditional GR&amp;R level and suggested how to improve the measurement.",
   "Tracked CPK, FPY and UPH against PVT criteria (FPY ≥ 95%, Cpk ≥ 1.33, UPH ≥ 90); wrote unit tests for the test and statistics code."]),
  ("Data Processing &amp; Report Automation Tool (Internal CLI Tool)","Python Developer · Python, Pandas, OpenPyXL, Regex, Schedule",[
   "Automated the end-of-day work of collecting and comparing data from 15–20 files (Excel, CSV, JSON) from operations teams, replacing manual filtering and copy-paste.",
   "Built a command-line (CLI) tool that reads and merges data from many sources; used Pandas and Regex to clean dates, phone numbers and transaction IDs, remove duplicates and separate bad rows.",
   "Built a module that compares data across sources to find differences and calculates summary numbers by group.",
   "Used OpenPyXL to export reports in the company's template and highlight unusual rows; used Schedule to run it every day.",
   "Result: daily report time dropped from over 1 hour to under 30 seconds, with no more manual-entry errors."]),
  ("System Monitoring &amp; Task Alert Bot","Python Developer · Python, Requests, Webhooks, Telegram API, Linux Cronjob",[
   "Problem: incidents were found slowly because logs and task progress were checked on several separate platforms.",
   "Built a background service on a Linux server (Cronjob) that scans system logs, checks internal services/APIs and gets task status from Redmine.",
   "Built a priority filter to flag unusual errors, stuck code reviews and tasks close to their deadline.",
   "Used Webhooks and the Telegram API to send alerts and an end-of-day summary to the team chat.",
   "Result: the team found and fixed incidents 50% sooner and saved time on daily manual checks."]),
  ("Corp - B2B Sales &amp; Salesforce Integration","Bac Ha · Team Lead · Small development team",[
   "Built a B2B sales management system on Odoo integrated with Salesforce to sync customer and business data.",
   "Led a small development team; customized quotation, sales order and pricing flows for business customers.",
   "Built the Odoo – Salesforce API for data mapping, syncing and error logging."]),
  ("Tan Phat ERP","Mate JSC · Team Lead · 11 months · 6 members (1 PM, 1 Team Lead, 3 Dev, 1 BA)",[
   "Delivered an ERP for Tan Phat Company (sales and e-commerce): Purchase, Sales, Loyalty, Website and CRM.",
   "Got requirements from the PM, planned and assigned tasks, and reviewed solutions and code."]),
  ("E-Contract","Mate JSC · 10 months · 9 members (1 PM, 2 BA, 2 QA, 4 Dev)",[
   "Built a contract management and e-signing solution on Odoo supporting PDF, DOCX, XML and USB Token signing.",
   "Built OWL components with drag-and-drop to set signature positions; managed documents from creation until signing is done.",
   "Built the USB Token plugin and XML signing with digital certificates; joined code reviews."])],
 edu=("Major: Information Technology","Hanoi Open University","03/2024 - Present"),
 out="LuuQuangHuy_CV_EN.pdf")

def render(d):
    body = f"""<!doctype html><html lang="{d['lang']}"><head><meta charset="utf-8"><title>Luu Quang Huy CV</title><style>{CSS}</style></head><body>
<div class="contact"><span>✉ huylq25122000@gmail.com</span><span>☎ 0983.840.617</span><span>⌖ {d['contact_loc']}</span></div>
<div class="head"><h1>Lưu Quang Huy</h1><div>{d['title']}</div></div><div class="page">
<h2>{d['h_sum']}</h2><div>{d['summary']}</div>
<h2>{d['h_skill']}</h2><div>Python · SQL · JavaScript · Git · Docker · Linux · API &amp; Webhook · REST API · Pandas · OpenPyXL</div>
<h2>{d['h_exp']}</h2>{jobs(d['exp'])}
<h2>{d['h_proj']}</h2><div class="role">{d['role']}</div>{projs(d['proj'])}
<h2>{d['h_edu']}</h2><div class="edu"><b>{d['edu'][0]}</b><br><span class="co">{d['edu'][1]}</span><br>{d['edu'][2]}</div>
</div></body></html>"""
    src = HERE / f"cv_{d['lang']}.html"
    src.write_text(body, encoding="utf-8")
    subprocess.run(["google-chrome", "--headless", "--no-sandbox", "--disable-gpu", "--no-pdf-header-footer",
                    "--virtual-time-budget=8000", f"--print-to-pdf={OUT / d['out']}", src.as_uri()], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

for d in (VI, EN): render(d)
