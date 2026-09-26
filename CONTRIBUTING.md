# Contributing

Run the standard checks before opening a pull request:

~~~bash
python -m unittest discover -s tests -v
PYTHONPATH=. python -m cleanroom.cli --help
~~~

Keep the project standard-library-only unless a dependency is clearly necessary.
