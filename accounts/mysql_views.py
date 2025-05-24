import mysql.connector
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

class ProductDataView(APIView):

    def get(self, request, barcode):
        try:
            # Connect to the MySQL database
            connection = mysql.connector.connect(
                host="103.97.126.29",
                user="vvesnzbk_product_data",
                password="Nguyen2004nam@",
                database="vvesnzbk_product_data"
            )

            cursor = connection.cursor(dictionary=True)

            # Query the product data using a partial match for the barcode
            query = "SELECT * FROM product_data WHERE item_barcode LIKE %s"
            cursor.execute(query, (f"%{barcode}%",))
            results = cursor.fetchall()

            # Close the connection
            cursor.close()
            connection.close()

            if results:
                return Response({"message": "Product data retrieved successfully", "data": results}, status=status.HTTP_200_OK)
            else:
                return Response({"message": "No product found matching the given barcode"}, status=status.HTTP_404_NOT_FOUND)

        except mysql.connector.Error as err:
            return Response({"error": str(err)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
