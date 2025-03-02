FROM python:3.11-slim

WORKDIR /usr/src/

RUN apt-get update && apt-get install -y libcurl4 git 

# Install dependencies

RUN pip install --no-cache-dir optuna psycopg2-binary mlflow \
    && pip install --no-cache-dir torch==2.0.1+cpu \
        --index-url https://download.pytorch.org/whl/cpu \
    && pip install pytorch-lightning \
    && pip install prometheus-flask-exporter \
    && pip install numpy==1.26.4 \
    && pip install scikit-learn

COPY pytorch_lightning_distributed.py .
COPY check_study.sh .

# Expose the port for the Flask application
EXPOSE 5000

# Set the entrypoint to run the script
ENTRYPOINT ["python", "pytorch_lightning_distributed.py"]
