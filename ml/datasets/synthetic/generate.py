"""Corpus d'entreprise SYNTHÉTIQUE (société et employés fictifs « Nordia Systems »).
Sortie : data/synthetic/docs.jsonl (une ligne par version) + fichiers .txt par département.
Chaque fait (question, réponse) apparaît mot pour mot dans le texte : il sert de vérité terrain pour la pertinence."""
import argparse
from pathlib import Path

from ml.datasets.common import write_jsonl

CO = "Nordia Systems"
ALL = ["CEO", "HR_MANAGER", "HR_EMPLOYEE", "IT_MANAGER", "IT_EMPLOYEE", "FINANCE_MANAGER", "FINANCE_EMPLOYEE", "GENERAL_EMPLOYEE"]
HR, HR_M = ["HR_MANAGER", "HR_EMPLOYEE"], ["HR_MANAGER"]
IT, IT_M = ["IT_MANAGER", "IT_EMPLOYEE"], ["IT_MANAGER"]
FIN, FIN_M = ["FINANCE_MANAGER", "FINANCE_EMPLOYEE"], ["FINANCE_MANAGER", "CEO"]


def S(title: str, *paras: str) -> str:
    return f"## {title}\n\n" + "\n\n".join(paras)


def doc(doc_id, title, dept, cls, roles, versions):
    """versions : liste de (texte, faits[(q, a)], statut, date)"""
    rows = []
    for i, (text, facts, status, date) in enumerate(versions, 1):
        rows.append({"doc_id": doc_id, "title": title, "department": dept, "classification": cls, "allowed_roles": roles,
                     "version": i, "status": status, "created_at": date, "updated_at": date,
                     "text": f"# {title}\n\n{text}", "facts": [{"question": q, "answer": a} for q, a in facts],
                     "source": "synthetic"})
    return rows


def build() -> list[dict]:
    d = []
    # ---------- HR ----------
    def handbook(hours, remote):
        return (S("Purpose", f"This employee handbook describes working conditions at {CO}. It applies to every employee in all departments."),
                S("Working hours", f"Standard working hours at {CO} are {hours}. Employees take a one hour lunch break."),
                S("Remote work", f"Employees may work remotely up to {remote} per week with manager approval."),
                S("Dress code", "Business casual clothing is expected in client-facing meetings."))
    h1, h2 = handbook("9:00 to 17:00", "two days"), handbook("8:30 to 16:30", "three days")
    d += doc("HR-HANDBOOK", "Employee Handbook", "HR", "INTERNAL", ALL, [
        ("\n\n".join(h1), [("What are the standard working hours?", "9:00 to 17:00")], "ARCHIVED", "2025-01-10"),
        ("\n\n".join(h2), [("What are the standard working hours?", "8:30 to 16:30"),
                           ("How many remote days per week are allowed?", "three days")], "ACTIVE", "2026-01-12")])
    leave = lambda n, carry: "\n\n".join((
        S("Annual leave", f"Every full-time employee receives {n} days of paid annual leave per calendar year."),
        S("Carry over", f"Employees may carry over a maximum of {carry} unused leave days into the following year."),
        S("Requests", "Leave requests must be submitted at least two weeks in advance through the HR portal."),
        S("Sick leave", "Sick leave of more than three consecutive days requires a medical certificate.")))
    d += doc("HR-LEAVE", "Leave Policy", "HR", "INTERNAL", ALL, [
        (leave(25, 5), [("How many days of annual leave do employees receive?", "25 days of paid annual leave")], "ARCHIVED", "2025-02-01"),
        (leave(28, 7), [("How many days of annual leave do employees receive?", "28 days of paid annual leave"),
                        ("How many unused leave days can be carried over?", "maximum of 7 unused leave days")], "ACTIVE", "2026-02-01")])
    d += doc("HR-RECRUIT", "Recruitment Policy", "HR", "INTERNAL", HR + ["CEO"], [(
        "\n\n".join((S("Process", "Every vacancy is published internally for ten working days before external advertising."),
                     S("Interviews", "Each candidate is interviewed by at least two people, including one member of the hiring department."),
                     S("Probation", "New hires serve a probation period of three months, extendable once by three months."),
                     S("References", "Reference checks are performed only after a written offer is accepted by the candidate."))),
        [("How long is the probation period for new hires?", "probation period of three months"),
         ("How many days is a vacancy published internally?", "ten working days")], "ACTIVE", "2026-01-20")])
    d += doc("HR-CONTRACT", "Employment Contract Template", "HR", "CONFIDENTIAL", HR_M, [(
        "\n\n".join((S("Parties", f"This contract is concluded between {CO} and the employee Amel Rezgui (fictional), hired as Software Developer."),
                     S("Notice period", "Either party may terminate the contract with a notice period of two months."),
                     S("Confidentiality", "The employee shall not disclose confidential company information during or after employment."),
                     S("Non-compete", "The non-compete obligation lasts twelve months after termination within the same market."))),
        [("What is the notice period in the employment contract?", "notice period of two months"),
         ("How long does the non-compete obligation last?", "twelve months after termination")], "ACTIVE", "2026-03-02")])
    d += doc("HR-SALARY", "Salary Grid 2026", "HR", "RESTRICTED", HR_M, [(
        "\n\n".join((S("Grid", "Junior engineers are paid between 1800 and 2400 dinars per month. Senior engineers are paid between 3500 and 4800 dinars per month."),
                     S("Bonuses", "The annual performance bonus ranges from one to three months of base salary."),
                     S("Executive", "The compensation of the HR director is 6200 dinars per month plus bonus."))),
        [("What is the monthly salary range of senior engineers?", "between 3500 and 4800 dinars per month"),
         ("What is the compensation of the HR director?", "6200 dinars per month")], "ACTIVE", "2026-01-05")])
    # ---------- IT ----------
    pw = lambda n, rot: "\n\n".join((
        S("Length", f"Passwords must contain at least {n} characters including upper case, lower case and digits."),
        S("Rotation", f"Privileged account passwords are rotated every {rot} days."),
        S("Storage", "Passwords must be stored only in the approved company password manager."),
        S("MFA", "Multi-factor authentication is mandatory for VPN and administrative access.")))
    d += doc("IT-PASSWORD", "Password Policy", "IT", "INTERNAL", ALL, [
        (pw(8, 180), [("How many characters must a password contain?", "at least 8 characters")], "ARCHIVED", "2025-03-01"),
        (pw(14, 90), [("How many characters must a password contain?", "at least 14 characters"),
                      ("How often are privileged passwords rotated?", "rotated every 90 days")], "ACTIVE", "2026-03-01")])
    d += doc("IT-SECURITY", "IT Security Policy", "IT", "CONFIDENTIAL", IT, [(
        "\n\n".join((S("Network", "The production network is segmented into three zones: public, internal and restricted."),
                     S("Patching", "Critical security patches must be deployed within 72 hours of release."),
                     S("Backups", "Backups of production databases run every night at 02:00 and are retained for 35 days."),
                     S("Incident reporting", "Any suspected security incident must be reported to the IT security desk within one hour."))),
        [("Within how many hours must critical patches be deployed?", "within 72 hours of release"),
         ("How long are production backups retained?", "retained for 35 days"),
         ("When must a security incident be reported?", "within one hour")], "ACTIVE", "2026-02-15")])
    d += doc("IT-INCIDENT-0326", "Incident Report 2026-03", "IT", "CONFIDENTIAL", IT_M, [(
        "\n\n".join((S("Summary", "On 14 March 2026 a phishing email led to the compromise of one employee mailbox at Nordia Systems."),
                     S("Root cause", "The root cause was a missing multi-factor authentication policy on the legacy mail gateway."),
                     S("Impact", "No customer data was exfiltrated. Approximately 40 internal emails were read by the attacker."),
                     S("Remediation", "MFA was enforced on all mail accounts and the legacy gateway was decommissioned on 21 March."))),
        [("What was the root cause of the March 2026 phishing incident?", "missing multi-factor authentication policy on the legacy mail gateway"),
         ("When was the legacy mail gateway decommissioned?", "decommissioned on 21 March")], "ACTIVE", "2026-03-25")])
    d += doc("IT-INFRA", "Infrastructure Documentation", "IT", "CONFIDENTIAL", IT, [(
        "\n\n".join((S("Hosting", "Production workloads run on a three-node Kubernetes cluster hosted in the Tunis data center."),
                     S("Database", "The primary PostgreSQL database replicates synchronously to a standby in a second availability zone."),
                     S("Monitoring", "Metrics are collected by Prometheus and alerts are routed to the on-call engineer."),
                     S("Disaster recovery", "The recovery time objective for core services is four hours and the recovery point objective is fifteen minutes."))),
        [("What is the recovery time objective for core services?", "recovery time objective for core services is four hours"),
         ("What tool collects infrastructure metrics?", "Prometheus")], "ACTIVE", "2026-02-20")])
    # ---------- Finance ----------
    d += doc("FIN-BUDGET", "Financial Budget 2026", "FINANCE", "RESTRICTED", FIN_M, [(
        "\n\n".join((S("Overview", f"The total approved operating budget of {CO} for 2026 is 4.2 million dinars."),
                     S("Allocation", "Engineering receives 45 percent of the budget, sales and marketing 25 percent and administration 15 percent."),
                     S("Reserve", "A contingency reserve of 10 percent is held by the finance department."))),
        [("What is the total operating budget for 2026?", "4.2 million dinars"),
         ("What share of the budget goes to engineering?", "Engineering receives 45 percent")], "ACTIVE", "2026-01-08")])
    exp = lambda lim, days: "\n\n".join((
        S("Approval", f"Expenses above {lim} dinars require written approval from the department manager."),
        S("Reimbursement", f"Approved expense claims are reimbursed within {days} working days."),
        S("Receipts", "Every claim must include an original receipt or a legible scan.")))
    d += doc("FIN-EXPENSE", "Expense Policy", "FINANCE", "INTERNAL", ALL, [
        (exp(200, 30), [("From what amount do expenses need manager approval?", "above 200 dinars")], "ARCHIVED", "2025-04-01"),
        (exp(500, 15), [("From what amount do expenses need manager approval?", "above 500 dinars"),
                        ("How fast are approved expense claims reimbursed?", "within 15 working days")], "ACTIVE", "2026-04-01")])
    d += doc("FIN-INVOICE", "Invoice Procedures", "FINANCE", "INTERNAL", FIN + ["CEO"], [(
        "\n\n".join((S("Issuing", "Customer invoices are issued within five days of delivery and carry a payment term of 45 days."),
                     S("Supplier invoices", "Supplier invoices are matched against purchase orders before payment is released."),
                     S("Late payment", "Overdue customer invoices trigger a reminder after 7 days and an escalation after 30 days."))),
        [("What is the payment term on customer invoices?", "payment term of 45 days"),
         ("When is a reminder sent for overdue invoices?", "reminder after 7 days")], "ACTIVE", "2026-02-10")])
    # ---------- Policies ----------
    d += doc("POL-PROCEDURES", "Internal Company Procedures", "POLICIES", "INTERNAL", ALL, [(
        "\n\n".join((S("Visitors", "All visitors must register at reception and wear a visitor badge at all times."),
                     S("Equipment", "Company laptops must be returned to the IT desk within five working days after an employee leaves."),
                     S("Meeting rooms", "Meeting rooms are booked through the shared calendar and released after fifteen minutes if unused."))),
        [("Within how many days must laptops be returned after departure?", "within five working days")], "ACTIVE", "2026-01-15")])
    d += doc("POL-CONDUCT", "Code of Conduct", "POLICIES", "PUBLIC", ALL, [(
        "\n\n".join((S("Respect", "Employees treat colleagues, customers and partners with respect and do not tolerate harassment."),
                     S("Conflicts of interest", "Employees must declare any personal interest that could conflict with company business."),
                     S("Whistleblowing", "Concerns can be reported confidentially to the ethics committee without fear of retaliation."))),
        [("Who receives confidential whistleblowing reports?", "ethics committee")], "ACTIVE", "2026-01-15")])
    d += doc("POL-STRATEGY", "Executive Strategy Memo", "POLICIES", "RESTRICTED", ["CEO"], [(
        "\n\n".join((S("Vision", "The board approved a three-year plan to expand into two new regional markets."),
                     S("Acquisition", "A confidential acquisition target in the logistics software sector is under evaluation."))),
        [("Which sector is the acquisition target in?", "logistics software sector")], "ACTIVE", "2026-02-28")])
    d += doc("POL-DRAFT", "Travel Policy (draft)", "POLICIES", "INTERNAL", ALL, [(
        S("Draft", "Business travel above 800 dinars will require director approval. This draft is not yet approved."),
        [], "DRAFT", "2026-04-10")])
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/synthetic/docs.jsonl")
    ap.add_argument("--data-dir", default="data")
    a = ap.parse_args()
    rows = build()
    n = write_jsonl(a.out, rows)
    folder = {"HR": "HR", "IT": "IT", "FINANCE": "Finance", "POLICIES": "Policies"}
    for r in rows:
        p = Path(a.data_dir) / folder[r["department"]] / f"{r['doc_id']}_v{r['version']}.txt"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(r["text"], encoding="utf-8")
    print(f"{n} document versions ({len({r['doc_id'] for r in rows})} documents) -> {a.out}")


if __name__ == "__main__":
    main()
