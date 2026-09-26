FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt pyproject.toml ./
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd -m forge && chown -R forge:forge /app
COPY forge.py forge_loop.py forge_agents.py forge_memory.py forge_skills.py forge_sandbox.py forge_router.py forge_obs.py forge_govern.py forge_consolidate.py forge_const.py forge_system_prompt.xml ./
COPY examples/ examples/
COPY tests/ tests/
COPY memory.md skills.md life.md ARCHITECTURE.md README.md ./
RUN chown -R forge:forge /app
USER forge
ENV FORGE_OFFLINE=1
ENV FORGE_LIGHT=1
ENV FORGE_VECTOR=file
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONSAFEPATH=1
HEALTHCHECK --interval=60s --timeout=10s --retries=2 CMD python -c "import forge_const; print('ok')"
CMD python forge_loop.py --run-file examples/demo_task.py
