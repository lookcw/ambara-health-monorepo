const Footer = () => {
  return (
    <footer className="border-t border-border bg-muted/30">
      <div className="container mx-auto px-4 py-12">
        <div className="flex flex-col md:flex-row justify-between items-center gap-4">
          <div className="flex items-center gap-2">
            <span className="text-lg font-bold text-primary">ambara</span>
            <span className="text-lg font-bold">health</span>
          </div>
          <p className="text-sm text-muted-foreground">
            © 2026 ambara health. All rights reserved.
          </p>
        </div>
      </div>
    </footer>
  );
};

export default Footer;
