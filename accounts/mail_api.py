from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

class SendEmailAPIView(APIView):
    def post(self, request):
        to_email = request.data.get("to_email")
        subject = request.data.get("subject")
        body_html = request.data.get("body_html")

        signature = """
        <hr>
        <div style=\"font-size: 14px; color: #555555;\">
          Trân trọng,<br>
          <strong style=\"color: #3498db; font-size: 16px;\">Thành Nam</strong><br>
          <span style=\"color: #888;\">Founder @ nguyenthanhnam.io.vn</span><br>
          <a href=\"https://nguyenthanhnam.io.vn/wp\" style=\"color: #3498db; text-decoration: none;\">
            https://nguyenthanhnam.io.vn/wp
          </a>
        </div>
        """

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = "thanhnamsuken@gmail.com"
        msg["To"] = to_email

        full_html = f"{body_html}{signature}"
        msg.attach(MIMEText(full_html, "html"))

        try:
            with smtplib.SMTP("smtp.gmail.com", 587) as server:
                server.starttls()
                server.login("thanhnamsuken@gmail.com", "hnvjgqonbzpsxnvk")
                server.sendmail(msg["From"], msg["To"], msg.as_string())
            return Response({"message": "✅ Gửi email thành công"}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
