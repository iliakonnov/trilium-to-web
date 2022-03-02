# Usage
Please change all four `XXX` to whatever values you have.
```
wget \
	--header "Cookie: trilium.sid=XXX; _csrf=XXX" \
	http://localhost:37840/api/notes/XXX/export/subtree/html/1.0/XXXS \
	-O Public.zip

python -m gen Public.zip
```

# TODO
- [ ] write better readme
- [ ] dark theme

