.PHONY: test verify demo-stat demo-metrica report run

test:
	python -m pytest -q --cov=fdd --cov-report=term-missing

verify:
	python verify_release.py

demo-stat:
	python pipeline.py statsbomb --demo --out output

demo-metrica:
	python pipeline.py metrica --demo --out output

report:
	python demo_report.py --out demo_report.html

run:
	streamlit run app.py
