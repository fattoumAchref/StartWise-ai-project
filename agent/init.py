from agent.tools.parser import parse_founder_input
from agent.tools.validator import validate_financial_context


__all__ = ["parse_founder_input", "validate_financial_context"]


if __name__ == "__main__":
    demo_text = "MRR 10000, burn 15000, cash 30000, 50 clients, on veut lever."
    context = parse_founder_input(demo_text)
    validation = validate_financial_context(context)
    print(context)
    print(validation)
