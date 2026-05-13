HOST ?= overleaf

.PHONY: deploy ping check

deploy:
	ansible-playbook playbooks/deploy.yml --limit $(HOST)

ping:
	ansible $(HOST) -m ping

check:
	ansible-playbook playbooks/deploy.yml --limit $(HOST) --check --diff
