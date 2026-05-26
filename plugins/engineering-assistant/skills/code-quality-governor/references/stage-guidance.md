# Code Quality Governor 阶段指引

检查项：
- 执行前必须读取 artifacts/_control/quality-contract.json、control-health-report.json、technology-adoption-report.json 和任务规则包
- build
- format
- lint
- typecheck
- unit_test
- integration_test
- coverage
- dependency_scan
- secret_scan
- migration_check
- architecture_boundary_check
- sonar_bugs_vulnerabilities_smells
- qodana_inspections_sarif
- checkstyle_style_rules
- cyclomatic_complexity
- duplication
- maintainability_reliability_security
