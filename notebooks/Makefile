.PHONY: install clean-outputs git-init notebook

install:
	uv sync

clean-outputs:
	uv run nbstripout *.ipynb

git-init:
	uv run nbstripout --install --attributes ../.gitattributes

notebook:
	uv run jupyter notebook
