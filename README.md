jsonescape
==

- ingest.py			sample ingest stream with mangled data
- jsonescape.py		filter that escapes broken json in incoming linestream

so you have an ingest stream producing json but it's inputs weren't escaped correctly so now your json is mangled and you see something like:

	$ ./ingest.py |jq .
	jq: parse error: Invalid literal at line 1, column 133

jsonescape will take any nested json and escape it so the base json passes muster:

	$ ./ingest.py |./jsonescape.py |jq -s '.[0]'
	{
	...
	}

mostly written as a test case for making a simple double predicate grammar and wrapping dsl in python
