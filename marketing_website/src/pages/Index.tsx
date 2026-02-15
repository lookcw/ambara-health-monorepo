import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { HeartPulse, ArrowRight, CheckCircle, Phone, Bell, Users, AlertTriangle, ClipboardList, Calendar } from "lucide-react";
import { Link } from "react-router-dom";
import heroDoctorImage from "@/assets/hero-doctor-2.svg";

const Index = () => {
  return (
    <div className="min-h-screen">
      {/* Header */}
      <header className="fixed top-0 left-0 right-0 z-50 bg-background/80 backdrop-blur-md border-b border-border">
        <div className="container mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <HeartPulse className="h-8 w-8 text-primary" />
            <span className="text-xl font-bold text-primary">Ambara Health</span>
          </div>

          <div className="flex items-center gap-3">
            <Button variant="ghost" size="sm" asChild>
              <Link to="/team">
                Team
              </Link>
            </Button>
            <Button size="sm" asChild>
              <a href="https://form.typeform.com/to/awtQDiTB" target="_blank" rel="noopener noreferrer">
                Contact Us
              </a>
            </Button>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <section className="relative overflow-hidden bg-gradient-to-b from-background via-accent/5 to-background pt-20 pb-20 px-4 min-h-[calc(100vh-64px)]">
        <div className="container mx-auto">
          <div className="grid gap-12 lg:grid-cols-2 lg:gap-16 items-center max-w-7xl mx-auto">
            <div className="space-y-8">
              <h1 className="text-5xl lg:text-6xl font-bold leading-tight">
                <span className="text-primary">Outbound Referral Management Made Easy</span>
              </h1>

              <div className="text-lg lg:text-xl text-muted-foreground leading-relaxed space-y-4">
                <p>
                  Ambara Health helps clinics increase completed referrals and reduce staff burden. We work closely with radiology clinics and specialists to ensure patients follow through and return for their follow-up care.
                </p>
                <ul className="space-y-3 text-left">
                  <li className="flex items-start gap-3">
                    <CheckCircle className="w-5 h-5 text-primary mt-0.5 flex-shrink-0" />
                    <span>Increase the rate of completed referrals</span>
                  </li>
                  <li className="flex items-start gap-3">
                    <CheckCircle className="w-5 h-5 text-primary mt-0.5 flex-shrink-0" />
                    <span>Reduce staff time spent chasing referrals</span>
                  </li>
                  <li className="flex items-start gap-3">
                    <CheckCircle className="w-5 h-5 text-primary mt-0.5 flex-shrink-0" />
                    <span>Auto-check if patient's insurance is accepted by the specific provider</span>
                  </li>
                </ul>
              </div>

              <div className="flex flex-col sm:flex-row gap-4 pt-4">
                <Button variant="hero" size="lg" className="group" asChild>
                  <a href="https://form.typeform.com/to/awtQDiTB" target="_blank" rel="noopener noreferrer">
                    Schedule Demo
                    <ArrowRight className="ml-2 h-5 w-5 transition-transform group-hover:translate-x-1" />
                  </a>
                </Button>
              </div>
            </div>

            <div className="relative lg:h-[700px] xl:h-[800px] flex items-center justify-center">
              <div className="rounded-2xl overflow-hidden shadow-lg w-full">
                <img
                  src={heroDoctorImage}
                  alt="Healthcare provider conducting patient checkup"
                  className="w-full h-full object-contain scale-110"
                />
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Mission Section */}
      <section className="py-20 px-4 bg-muted/30">
        <div className="container mx-auto">
          <div className="max-w-3xl mx-auto text-center mb-16">
            <h2 className="text-4xl font-bold mb-6">Our Mission</h2>
            <p className="text-xl text-muted-foreground">
              Referral coordination is broken. Patients get lost between appointments, staff spend hours chasing follow-ups, and critical care gets delayed. Ambara Health automates the entire outbound referral workflow, from patient reminders to insurance verification to provider matching. We work closely with radiology clinics and specialists to ensure patients follow through on their referrals and come back for the care they need.
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-8 max-w-5xl mx-auto">
            <Card className="border-none shadow-lg">
              <CardContent className="pt-8 text-center">
                <div className="w-16 h-16 bg-primary/10 rounded-full flex items-center justify-center mx-auto mb-6">
                  <Bell className="w-8 h-8 text-primary" />
                </div>
                <h3 className="text-2xl font-bold mb-4">Automated Patient Reminders</h3>
                <p className="text-muted-foreground">
                  We text patients to remind them to schedule their referral appointments. Automated follow-ups ensure no referral falls through the cracks.
                </p>
              </CardContent>
            </Card>

            <Card className="border-none shadow-lg">
              <CardContent className="pt-8 text-center">
                <div className="w-16 h-16 bg-primary/10 rounded-full flex items-center justify-center mx-auto mb-6">
                  <Users className="w-8 h-8 text-primary" />
                </div>
                <h3 className="text-2xl font-bold mb-4">Smart Provider Matching</h3>
                <p className="text-muted-foreground">
                  Help patients find the best provider based on your clinic's guidance and insurance acceptance. No more surprise out-of-network bills.
                </p>
              </CardContent>
            </Card>

            <Card className="border-none shadow-lg">
              <CardContent className="pt-8 text-center">
                <div className="w-16 h-16 bg-accent rounded-full flex items-center justify-center mx-auto mb-6">
                  <AlertTriangle className="w-8 h-8 text-accent-foreground" />
                </div>
                <h3 className="text-2xl font-bold mb-4">Early Alert System</h3>
                <p className="text-muted-foreground">
                  Get notified if a patient doesn't follow through, so none of your visits are wasted. Intervene early before patients fall off the care pathway.
                </p>
              </CardContent>
            </Card>
          </div>
        </div>
      </section>

      {/* How It Works Section */}
      <section className="py-20 px-4 bg-gradient-to-b from-background via-accent/5 to-background">
        <div className="container mx-auto">
          <div className="max-w-3xl mx-auto text-center">
            <h2 className="text-4xl font-bold mb-6">How It Works</h2>
            <p className="text-xl text-muted-foreground mb-8">
              We give you a fax number to send referrals to, and we take care of the rest.
            </p>
            <div className="grid md:grid-cols-3 gap-8 text-left">
              <div className="text-center">
                <div className="w-12 h-12 bg-primary text-primary-foreground rounded-full flex items-center justify-center mx-auto mb-4 text-xl font-bold">1</div>
                <h3 className="font-bold mb-2">Fax Your Referral</h3>
                <p className="text-muted-foreground">Send referrals to your dedicated Ambara Health fax number. Works with or without a receiving provider specified.</p>
              </div>
              <div className="text-center">
                <div className="w-12 h-12 bg-primary text-primary-foreground rounded-full flex items-center justify-center mx-auto mb-4 text-xl font-bold">2</div>
                <h3 className="font-bold mb-2">We Start Scheduling</h3>
                <p className="text-muted-foreground">The referral appears on your dashboard and we begin reaching out to the patient to schedule their appointment.</p>
              </div>
              <div className="text-center">
                <div className="w-12 h-12 bg-primary text-primary-foreground rounded-full flex items-center justify-center mx-auto mb-4 text-xl font-bold">3</div>
                <h3 className="font-bold mb-2">Track Progress</h3>
                <p className="text-muted-foreground">Monitor every referral in real-time. Get alerts if a patient isn't following through.</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Solutions Section */}
      <section className="py-20 px-4">
        <div className="container mx-auto">
          <div className="max-w-3xl mx-auto text-center mb-16">
            <h2 className="text-4xl font-bold mb-6">Our Focus Areas</h2>
            <p className="text-xl text-muted-foreground">
              We automate your outbound referral workflow so patients get the care they need and your staff can focus on what matters. We partner with radiology clinics and specialists to close the loop on every referral.
            </p>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-8 max-w-6xl mx-auto">
            <Card className="border-none shadow-md h-full">
              <CardContent className="pt-8">
                <div className="w-16 h-16 bg-primary/10 rounded-full flex items-center justify-center mb-6">
                  <Phone className="w-8 h-8 text-primary" />
                </div>
                <h3 className="text-2xl font-bold mb-4">
                  Multi-Channel Outreach
                </h3>
                <p className="text-muted-foreground">
                  Automated texts, calls, and emails to help patients schedule their referral appointments. Patients can communicate however they prefer.
                </p>
              </CardContent>
            </Card>

            <Card className="border-none shadow-md h-full">
              <CardContent className="pt-8">
                <div className="w-16 h-16 bg-primary/10 rounded-full flex items-center justify-center mb-6">
                  <ClipboardList className="w-8 h-8 text-primary" />
                </div>
                <h3 className="text-2xl font-bold mb-4">
                  Provider & Plan Directory
                </h3>
                <p className="text-muted-foreground">
                  We maintain a list of eligible providers and the plans they accept. You'll never need to call to ask if a provider takes a plan again.
                </p>
              </CardContent>
            </Card>

            <Card className="border-none shadow-md h-full">
              <CardContent className="pt-8">
                <div className="w-16 h-16 bg-primary/10 rounded-full flex items-center justify-center mb-6">
                  <Calendar className="w-8 h-8 text-primary" />
                </div>
                <h3 className="text-2xl font-bold mb-4">
                  Follow-Up Tracking
                </h3>
                <p className="text-muted-foreground">
                  We track when each patient's follow-up with you should be, so you know early if they're off track.
                </p>
              </CardContent>
            </Card>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-border bg-muted/30 py-12 px-4">
        <div className="container mx-auto">
          <div className="flex flex-col md:flex-row justify-between items-center gap-4">
            <div className="flex items-center gap-2">
              <HeartPulse className="h-6 w-6 text-primary" />
              <span className="text-lg font-bold text-primary">Ambara Health</span>
            </div>
            <div className="flex items-center gap-6">
              <Link to="/team" className="text-sm text-muted-foreground hover:text-primary transition-colors">
                Team
              </Link>
              <p className="text-sm text-muted-foreground">
                © 2026 Ambara Health. All rights reserved.
              </p>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default Index;
