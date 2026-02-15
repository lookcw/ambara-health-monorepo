import { HeartPulse } from "lucide-react";

const HomeCareFooter = () => {
  return (
    <footer className="border-t border-border bg-muted/30 py-12 px-4">
      <div className="container mx-auto">
        <div className="flex flex-col items-center space-y-4">
          <div className="flex items-center gap-2">
            <HeartPulse className="h-6 w-6 text-primary" />
            <span className="text-lg font-bold text-primary">
              Ambara Health
            </span>
          </div>
          <p className="text-sm text-muted-foreground text-center">
            Making patient care clear and simple for caregivers everywhere.
          </p>
          <p className="text-sm text-muted-foreground">© 2026 Ambara Health. All rights reserved.</p>
        </div>
      </div>
    </footer>
  );
};

export default HomeCareFooter;
