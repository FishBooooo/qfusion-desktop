.PHONY: setup lint typecheck test test-backend test-frontend test-e2e run-backend run-desktop build-backend build-windows

setup lint typecheck test test-backend test-frontend test-e2e run-backend run-desktop build-backend build-windows:
	./scripts/run_in_qfusion_env.sh just $@
