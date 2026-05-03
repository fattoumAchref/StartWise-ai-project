"""
Main Investment Agent - orchestrates all modules.
"""

from finagents.investment.input_handler import InputHandler
from finagents.investment.stage_detector import StageDetector
from finagents.investment.valuation_engine import ValuationEngine
from finagents.investment.dilution_calculator import DilutionCalculator
from finagents.investment.scenario_generator import ScenarioGenerator
from finagents.investment.strategy_selector import StrategySelector
from finagents.investment.output_formatter import OutputFormatter
from finagents.investment.benchmark_engine import BenchmarkEngine
from finagents.investment.memory.store import save_analysis
from finagents.investment.memory.comparator import ProgressComparator


class InvestmentAgent:
    """
    Investment Agent MVP.
    
    Workflow:
    1. Validate input
    2. Detect stage
    3. Calculate valuation
    4. Generate scenarios
    5. Select optimal
    6. Calculate dilution
    7. Format output
    """
    
    def __init__(self):
        self.input_handler = InputHandler()
        self.stage_detector = StageDetector()
        self.valuation_engine = ValuationEngine()
        self.dilution_calculator = DilutionCalculator()
        self.scenario_generator = ScenarioGenerator()
        self.strategy_selector = StrategySelector()
        self.output_formatter = OutputFormatter()
        self.benchmark_engine = BenchmarkEngine(use_real_data=True)
        self.comparator = ProgressComparator()
    
    def analyze(self, finance_data: dict, marketing_data: dict,
                project_id: str = "default", user_id: str = "user_001") -> dict:
        """
        Main analysis method.
        
        Args:
            finance_data: Data from Finance Agent
            marketing_data: Data from Marketing Agent
        
        Returns:
            Investment recommendation dict
        """
        print("\n" + "="*70)
        print("INVESTMENT AGENT - STARTING ANALYSIS")
        print("="*70)
        
        # Step 1: Validate & extract
        print("\n[1/7] Validating input...")
        input_result = self.input_handler.validate_and_extract(
            finance_data, 
            marketing_data
        )
        
        if input_result["status"] == "error":
            return {"error": input_result["message"]}
        
        data = input_result["data"]
        print(f"      ✓ Revenue: {data['annual_revenue']:,.0f} TND")
        print(f"      ✓ Funding needed: {data['funding_needed']:,.0f} TND")
        
        # Step 2: Detect stage
        print("\n[2/7] Detecting startup stage...")
        stage = self.stage_detector.detect(data["annual_revenue"])
        data["stage"] = stage
        print(f"      ✓ Stage: {stage}")
        
        # Step 3: Calculate valuation
        print("\n[3/7] Calculating valuation...")
        valuation = self.valuation_engine.calculate(data)
        print(f"      ✓ Valuation: {valuation.final_valuation:,.0f} TND")
        print(f"      ✓ Method: {valuation.method_used}")

        # Step 3b: Enrich with real market benchmarks
        sector = data.get("sector") or data.get("industry", "tech")
        data["sector"] = sector  # normalize so downstream always uses "sector"
        bench = self.benchmark_engine.get_valuation_benchmark(sector, data["stage"], data["annual_revenue"])
        data["market_sample_size"] = bench.get("sample_size", 0)
        data["startup_act_rate"] = bench.get("startup_act_rate")
        data["available_grants"] = self.benchmark_engine.get_available_grants({
            "sector": sector,
            "company_age": data.get("company_age", 3),
            "tech_based": True,
            "has_export": data.get("has_export", False),
            "innovative": True,
        })
        print(f"      ✓ Market context: {data['market_sample_size']} similar startups in Tunisia")

        # Step 4: Generate scenarios
        print("\n[4/7] Generating funding scenarios...")
        scenarios = self.scenario_generator.generate(
            funding_needed=data["funding_needed"],
            valuation=valuation.final_valuation,
            data=data,
            available_grants=data.get("available_grants", []),
        )
        print(f"      ✓ Generated {len(scenarios)} scenarios")

        # Step 5: Select optimal
        print("\n[5/7] Selecting optimal strategy...")
        optimal = self.strategy_selector.select_optimal(scenarios, stage=data["stage"])
        print(f"      ✓ Selected: {optimal.name} (score: {optimal.score:.0f})")
        print(f"      ✓ Dilution: {optimal.dilution_pct:.1f}%")
        
        # Step 6: Calculate detailed dilution
        print("\n[6/7] Calculating dilution details...")
        dilution = self.dilution_calculator.calculate(
            pre_money=valuation.final_valuation,
            equity_amount=optimal.equity
        )
        print(f"      ✓ Founder dilution: {dilution.founder_dilution_pct:.1f}%")
        
        # Step 7: Format output
        print("\n[7/7] Formatting recommendation...")
        data["_all_scenarios"] = [
            {"name": s.name, "raise_amount": s.raise_amount,
             "dilution_pct": s.dilution_pct, "score": s.score}
            for s in scenarios
        ]
        recommendation = self.output_formatter.format(
            valuation=valuation,
            optimal_scenario=optimal,
            all_scenarios=scenarios,
            dilution=dilution,
            data=data
        )
        print("      ✓ Recommendation ready")

        print("\n" + "="*70)
        print("INVESTMENT AGENT - ANALYSIS COMPLETE")
        print("="*70)

        result = recommendation.to_dict()

        # Inject fields needed for memory storage
        result["data"]["stage"]            = data.get("stage")
        result["data"]["sector"]           = data.get("sector") or data.get("industry")
        result["data"]["annual_revenue"]   = data.get("annual_revenue")
        result["data"]["growth_rate"]      = data.get("growth_rate")
        result["data"]["available_grants"] = data.get("available_grants", [])

        # Save to memory
        save_analysis(project_id, user_id, result)

        # Progress comparison (only if previous sessions exist)
        progress = self.comparator.compare(project_id, result)
        if progress:
            result["progress_report"] = progress
            print("\n[Memory] Progress report generated")

        # Generate A2A message output
        a2a_msg = recommendation.to_a2a_message(
            project_id=project_id,
            session_id=result.get("timestamp", ""),
            to=["Orchestrator"],
            priority="high",
            requires_response=False,
            tags=[data.get("stage", ""), data.get("sector") or data.get("industry", "")],
        )
        result["a2a_message"] = a2a_msg

        # Write JSON file
        import json, os
        output_dir = os.path.join(os.path.dirname(__file__), "outputs")
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, f"{project_id}_latest.json")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(a2a_msg, f, indent=2, ensure_ascii=False)
        print(f"[Output] A2A message saved → {output_path}")

        return result