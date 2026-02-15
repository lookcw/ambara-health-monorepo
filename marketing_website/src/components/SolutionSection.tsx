import { DollarSign, Heart, TrendingDown } from "lucide-react";

const SolutionSection = () => {
  return (
    <section className="py-20 lg:py-32">
      <div className="container mx-auto px-4">
        <div className="text-center max-w-3xl mx-auto mb-16">
          <h2 className="text-3xl font-bold lg:text-5xl mb-6">
            A Better Way Forward
          </h2>
          <p className="text-lg text-muted-foreground">
            Ambara Health flips the script on healthcare costs. We pay your members to adhere to care, 
            creating a win-win for everyone.
          </p>
        </div>

        <div className="grid lg:grid-cols-3 gap-8 mb-16">
          <div className="text-center">
            <div className="w-16 h-16 mx-auto rounded-full bg-primary/10 flex items-center justify-center mb-6">
              <DollarSign className="w-8 h-8 text-primary" />
            </div>
            <h3 className="text-xl font-semibold mb-3">Members Get Rewarded</h3>
            <p className="text-muted-foreground">
              Direct financial incentives for following care plans and making healthy choices.
            </p>
          </div>

          <div className="text-center">
            <div className="w-16 h-16 mx-auto rounded-full bg-primary/10 flex items-center justify-center mb-6">
              <Heart className="w-8 h-8 text-primary" />
            </div>
            <h3 className="text-xl font-semibold mb-3">Engagement Soars</h3>
            <p className="text-muted-foreground">
              Higher member engagement means better health outcomes across your workforce.
            </p>
          </div>

          <div className="text-center">
            <div className="w-16 h-16 mx-auto rounded-full bg-primary/10 flex items-center justify-center mb-6">
              <TrendingDown className="w-8 h-8 text-primary" />
            </div>
            <h3 className="text-xl font-semibold mb-3">Costs Drop</h3>
            <p className="text-muted-foreground">
              Lower healthcare costs for self-funded and level-funded plans through prevention.
            </p>
          </div>
        </div>

        <div className="bg-accent rounded-2xl p-8 lg:p-12">
          <div className="max-w-2xl mx-auto text-center">
            <h3 className="text-2xl font-bold mb-4">
              Designed for Self-Funded & Level-Funded Plans
            </h3>
            <p className="text-accent-foreground/80">
              Our model works because when your members stay healthy, you save money. 
              We've proven that paying members to adhere to care dramatically reduces claims 
              while improving satisfaction and retention.
            </p>
          </div>
        </div>
      </div>
    </section>
  );
};

export default SolutionSection;
