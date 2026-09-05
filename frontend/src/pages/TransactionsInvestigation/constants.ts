/**
 * Filter options for the Transactions Investigation screen. Every option value
 * is a real value the backend accepts (statuses, payment methods and gateways
 * mirror the synthetic data pools), sorted for readability.
 */

export interface SelectOption {
  value: string;
  label: string;
}

export const STATUS_OPTIONS: SelectOption[] = [
  { value: '', label: 'All Statuses' },
  { value: 'failed', label: 'Failed' },
  { value: 'recovered', label: 'Recovered' },
  { value: 'pending', label: 'Pending' },
];

export const METHOD_OPTIONS: SelectOption[] = [
  { value: '', label: 'All Methods' },
  { value: 'card', label: 'Card' },
  { value: 'bank_transfer', label: 'Bank Transfer' },
  { value: 'wallet', label: 'Wallet' },
  { value: 'upi', label: 'UPI' },
];

const GATEWAY_LABELS: Record<string, string> = {
  stripe: 'Stripe',
  adyen: 'Adyen',
  braintree: 'Braintree',
  razorpay: 'Razorpay',
  paypal: 'PayPal',
  worldpay: 'Worldpay',
  chase: 'Chase',
  barclays: 'Barclays',
};

export const GATEWAY_OPTIONS: SelectOption[] = [
  { value: '', label: 'All Gateways' },
  ...Object.entries(GATEWAY_LABELS).map(([value, label]) => ({ value, label })),
];

export interface AppliedFilters {
  search: string;
  status: string;
  payment_method: string;
  gateway: string;
  date: string;
}

export const EMPTY_FILTERS: AppliedFilters = {
  search: '',
  status: '',
  payment_method: '',
  gateway: '',
  date: '',
};

export const PAGE_SIZE = 10;