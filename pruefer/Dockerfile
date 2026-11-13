# OMG SysML v2 Pilotimplementierung als Jupyter-Kernel (conda-forge, EPL-2.0), dazu ein kleiner Prüf- und Exportdienst.
FROM mambaorg/micromamba:1.5.10
RUN micromamba install -y -n base -c conda-forge python=3.11 jupyter_client ipykernel jupyter-sysml-kernel && micromamba clean -a -y
COPY dienst.py /opt/pruefer/dienst.py
ENV PATH=/opt/conda/bin:$PATH HOME=/tmp
EXPOSE 8100
CMD ["python", "/opt/pruefer/dienst.py"]
