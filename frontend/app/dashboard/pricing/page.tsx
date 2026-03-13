import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

export default function PricingPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Pricing &amp; Plans</h1>

      <div className="grid gap-6 md:grid-cols-3 pt-6">
        {/* Free Plan */}
        <Card>
          <CardHeader>
            <CardTitle className="text-xl">Free</CardTitle>
            <CardDescription>
              <span className="text-3xl font-bold text-foreground">$0</span>
              <span className="text-sm">/mo</span>
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2 text-sm">
              <li>– 3 Integrations</li>
              <li>– 1,000 Documents</li>
              <li>– Basic Search</li>
            </ul>
          </CardContent>
          <CardFooter>
            <Button variant="secondary" className="w-full">
              Current Plan
            </Button>
          </CardFooter>
        </Card>

        {/* Pro Plan */}
        <Card className="border-2 border-primary relative overflow-hidden">
          <Badge className="absolute top-0 right-0 rounded-none rounded-bl-lg">
            POPULAR
          </Badge>
          <CardHeader>
            <CardTitle className="text-xl">Pro</CardTitle>
            <CardDescription>
              <span className="text-3xl font-bold text-foreground">$20</span>
              <span className="text-sm">/mo</span>
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2 text-sm">
              <li>– Unlimited Integrations</li>
              <li>– 50,000 Documents</li>
              <li>– RAG AI Chat</li>
              <li>– Priority Support</li>
            </ul>
          </CardContent>
          <CardFooter>
            <Button className="w-full">Upgrade</Button>
          </CardFooter>
        </Card>
      </div>
    </div>
  );
}
