FROM python:3.13

WORKDIR /mcp-expense-app

COPY ./requirements.txt .

RUN pip install -r requirements.txt

COPY ./client.demo.py .

EXPOSE 8501

CMD ["streamlit", "run", "client.demo.py"]
