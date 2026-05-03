"""
Main Investment Agent - orchestrates all modules.
"""

from agents.investment.input_handler import InputHandler
from agents.investment.stage_detector import StageDetector
from agents.investment.valuation_engine import ValuationEngine
from agents.investment.dilution_calculator import DilutionCalculator
from agents.investment.scenario_generator import ScenarioGenerator
from agents.investment.strategy_selector import StrategySelector
from agents.investment.output_formatter import OutputFormatter
from agents.investment.benchmark_engine import BenchmarkEngine
from agents.investment.deal_intelligence import ComparableTransactions, InvestorMatcher, TermSheetGenerator
from agents.investment.robustness import MultiRoundDilution, SensitivityAnalysis, ExitScenarios
from agents.investment.memory.store import save_analysis
from agents.investment.memory.comparator import ProgressComparator


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
        self.input_handler    = InputHandler()
        self.stage_detector   = StageDetector()
        self.valuation_engine = ValuationEngine()
        self.dilution_calculator = DilutionCalculator()
        self.scenario_generator = ScenarioGenerator()
        self.strategy_selector  = StrategySelector()
        self.output_formatter   = OutputFormatter()
        self.benchmark_engine   = BenchmarkEngine(use_real_data=True)
        self.comparables        = ComparableTransactions()
        self.investor_matcher   = InvestorMatcher()
        self.term_sheet_gen     = TermSheetGenerator()
        self.multi_round        = MultiRoundDilution()
        self.sensitivity        = SensitivityAnalysis()
        self.exit_scenarios     = ExitScenarios()
        self.comparator         = ProgressComparator()
    
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

        # Step 3c: Comparable transactions + investor matching
        print("\n[3c] Finding comparable deals & matching investors...")
        data["comparable_deals"] = self.comparables.find(
            sector=sector,
            funding_amount=data["funding_needed"],
            n=3,
        )
        data["matched_investors"] = self.investor_matcher.match(
            sector=sector,
            stage=stage,
            funding_amount=data["funding_needed"],
            top_n=5,
        )
        print(f"      ✓ Comparables: {len(data['comparable_deals'])} deals found")
        print(f"      ✓ Investors: {len(data['matched_investors'])} matched")

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

        # Step 6b: Generate term sheet
        print("\n[6b] Generating term sheet...")
        data["term_sheet"] = self.term_sheet_gen.generate(
            sector          = sector,
            stage           = stage,
            pre_money       = valuation.final_valuation,
            equity          = optimal.equity,
            post_money      = dilution.post_money,
            investor_pct    = dilution.new_investor_pct,
            founder_after_pct = dilution.founder_after_pct,
            raise_amount    = optimal.raise_amount,
            investors       = data.get("matched_investors", []),
        )
        print("      ✓ Term sheet ready")

        # Step 6c: Robustness analysis
        print("\n[6c] Computing robustness analysis...")
        data["multi_round_dilution"] = self.multi_round.compute(
            stage            = stage,
            current_raise    = optimal.raise_amount,
            current_premoney = valuation.final_valuation,
        )
        data["sensitivity"] = self.sensitivity.compute(
            annual_revenue = data["annual_revenue"],
            growth_rate    = data.get("growth_rate", 0.5),
            team_score     = data.get("team_score", 0.5),
            market_score   = data.get("market_score", 0.5),
            industry       = sector,
            base_valuation = valuation.final_valuation,
        )
        data["exit_scenarios"] = self.exit_scenarios.compute(
            annual_revenue    = data["annual_revenue"],
            growth_rate       = data.get("growth_rate", 0.5),
            industry          = sector,
            pre_money         = valuation.final_valuation,
            founder_after_pct = dilution.founder_after_pct,
        )
        print("      ✓ Robustness analysis ready")
        
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
        result["data"]["stage"]              = data.get("stage")
        result["data"]["sector"]             = data.get("sector") or data.get("industry")
        result["data"]["annual_revenue"]     = data.get("annual_revenue")
        result["data"]["growth_rate"]        = data.get("growth_rate")
        result["data"]["available_grants"]   = data.get("available_grants", [])
        result["data"]["comparable_deals"]      = data.get("comparable_deals", [])
        result["data"]["matched_investors"]     = data.get("matched_investors", [])
        result["data"]["term_sheet"]            = data.get("term_sheet", "")
        result["data"]["multi_round_dilution"]  = [
            {"round_name": r.round_name, "raise_amount": r.raise_amount,
             "pre_money": r.pre_money, "post_money": r.post_money,
             "investor_pct": r.investor_pct, "founder_pct": r.founder_pct}
            for r in data.get("multi_round_dilution", [])
        ]
        result["data"]["sensitivity"] = [
            {"assumption": s.assumption, "base_value": s.base_value,
             "minus_20": s.minus_20_val, "base": s.base_val,
             "plus_20": s.plus_20_val, "impact": s.impact}
            for s in data.get("sensitivity", [])
        ]
        result["data"]["exit_scenarios"] = [
            {"name": e.name, "exit_multiple": e.exit_multiple,
             "revenue_year5": e.revenue_year5, "exit_valuation": e.exit_valuation,
             "founder_proceeds": e.founder_proceeds, "roi_multiple": e.roi_multiple}
            for e in data.get("exit_scenarios", [])
        ]

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