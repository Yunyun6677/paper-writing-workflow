# v0.11 end-to-end evaluation

These tests use only synthetic fixtures created in temporary directories. They do not read private projects, licensed papers, credentials, or user data.

Run with:

```powershell
.\.venv-empirical\Scripts\python.exe -m unittest discover -s tests/e2e -p "test_*.py" -v
```

The suite exercises three complete project shapes and injects model timeout, malformed observation, missing artifact, tool timeout, network failure, duplicate side effect, process restart, checkpoint corruption, verifier rejection, and human rejection. A passing test proves the checked runtime contract only; it does not certify scientific validity or a live external model/provider.
