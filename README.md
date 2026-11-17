# November SQL Presentation

## Presentation title

**How an Analytics Team Turns Business Data into Management Decisions**

This master folder contains the fictional Riverbend Beverage Company project. The presentation follows data from source systems through PostgreSQL, SQL and Python pipelines, role-specific analysis, Power BI dashboards, forecasting, and management decisions.

## Start the online beverage store

Open PowerShell in:

```text
03_Data_Sources_and_Synthetic_Data\01_Online_Beverage_Store
```

Run:

```powershell
docker compose up --build -d
```

Then open:

- Storefront: http://localhost:8080
- FastAPI documentation: http://localhost:8000/docs
- API health check: http://localhost:8000/health

Use the promotion code `SUMMER10` during the demonstration.

## Folder guide

- `00_Project_Overview_and_Roadmap`: Scope, schedule, task list, and presentation sequence
- `01_Business_Context`: Riverbend company profile, departments, goals, and management problems
- `02_Analytics_Roles_and_Questions`: Questions and responsibilities for each analyst role
- `03_Data_Sources_and_Synthetic_Data`: Storefront, POS, inventory, supplier, API, and CSV sources
- `04_Data_Pipelines_and_Architecture`: ETL jobs, orchestration, validation, and architecture diagrams
- `05_SQL_and_Data_Models`: PostgreSQL scripts, staging tables, star schema, and SQL demonstrations
- `06_Dashboards_and_Decisions`: Power BI files, KPIs, role-specific dashboards, and recommendations
- `07_Forecasting_and_Machine_Learning`: Demand forecasting code, model results, and evaluation
- `08_PowerPoint_and_Speaker_Notes`: Final slide deck and presenter notes
- `09_Demo_and_Screenshots`: Backup screenshots, exported data, and live-demo materials

## Important data note

All company names, customers, orders, transactions, and business results in this project are fictitious or synthetic. The project does not process real payments.
# riverbend-end-to-end-data-analytics
An end-to-end data analytics demonstration featuring synthetic beverage sales data, Docker, PostgreSQL, Python, Power BI, and predictive analytics. Presented at the Capital Area SQL Server User Group (CASSUG).
