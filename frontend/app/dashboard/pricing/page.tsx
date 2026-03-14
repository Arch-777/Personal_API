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
      <h1 className="text-2xl font-bold">Pricing</h1>

      <Card className="relative overflow-hidden pt-2">
        <Badge className="absolute top-0 right-0 rounded-none rounded-bl-lg">
          PAY-AS-YOU-GO
        </Badge>
        <CardHeader>
          <CardTitle className="text-xl">Pay-as-you-go metered billing</CardTitle>
          <CardDescription>
            Bill only usage each month with no plan lock-in.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <p className="text-sm font-medium mb-2">Meter on:</p>
            <ul className="space-y-2 text-sm">
              <li>- Tokens processed</li>
              <li>- Search queries</li>
              <li>- Connector sync jobs</li>
              <li>- Storage GB</li>
            </ul>
          </div>

          <p className="text-sm text-muted-foreground">
            Why it fits: easiest &ldquo;fair pricing&rdquo; story vs competitors.
          </p>
        </CardContent>
        <CardFooter>
          <Button className="w-full">Contact Sales</Button>
        </CardFooter>
      </Card>
    </div>
  );
}