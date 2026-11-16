// Education loan guide for Indian students going abroad. Written by the site owner.
// Scheme rules and lender products change often. The page says so and sends readers to the official sources.
export const UPDATED = '15 November 2026';

export const SOURCES = {
  rbi: 'https://www.rbi.org.in/commonman/english/scripts/FAQs.aspx?Id=3372',
  pmv: 'https://pmvidyalaxmi.co.in/',
  vl: 'https://www.vidyalakshmi.co.in/',
  pib: 'https://static.pib.gov.in/WriteReadData/specificdocs/documents/2026/jul/doc2026729936401.pdf',
};

// Block types: p (paragraph), ul (items with an optional bold lead), tip, warn, link.
export const topics = [
  {
    id: 'rbi',
    n: '01',
    title: 'What are the RBI guidelines for education loans?',
    desc: 'The framework, and what it does not guarantee.',
    blocks: [
      { t: 'p', text: 'RBI’s education-loan FAQ refers to the Indian Banks’ Association (IBA) Model Education Loan Scheme. The scheme provides a model framework for banks; it is not one universal loan contract. Banks may have product-specific conditions and underwriting policies.' },
      { t: 'ul', items: [
        { text: 'Ask the bank which scheme and current policy it is applying.' },
        { text: 'RBI does not prescribe one common interest rate for every education loan.' },
        { text: 'Do not assume that every bank or NBFC offers identical terms.' },
        { text: 'NBFCs follow their own lending policies within the regulations applicable to them; the IBA model scheme does not automatically apply to them in the same way as participating banks.' },
      ] },
      { t: 'tip', text: 'Ask for the current product terms in writing. Compare the Key Facts Statement (KFS), sanction letter and loan agreement, not just a website headline.' },
      { t: 'link', href: SOURCES.rbi, text: 'Read RBI’s education-loan FAQs' },
    ],
  },
  {
    id: 'collateral',
    n: '02',
    title: 'Do you need collateral for an education loan?',
    desc: '₹4 lakh, ₹7.5 lakh and what those figures actually mean.',
    blocks: [
      { t: 'p', text: 'Collateral requirements depend on the applicable bank scheme, loan amount, guarantee eligibility and lender policy. Two different concepts are often confused: a bank’s collateral requirement and a credit guarantee that protects an eligible lender.' },
      { t: 'ul', items: [
        { lead: 'Up to ₹4 lakh:', text: 'the IBA Model Education Loan Scheme has traditionally provided for no collateral security or third-party guarantee, subject to its terms.' },
        { lead: 'Above ₹4 lakh:', text: 'check the bank’s current scheme and security requirements.' },
        { lead: 'CGFSEL:', text: 'the Credit Guarantee Fund Scheme for Education Loans has separate eligibility and coverage conditions. It does not mean every loan up to ₹7.5 lakh is automatically collateral-free.' },
        { lead: 'Higher unsecured loans:', text: 'some lenders may offer them for selected universities, courses or borrower profiles. These are lender-specific decisions.' },
      ] },
      { t: 'warn', text: 'Do not treat ₹7.5 lakh as a universal collateral-free entitlement. Ask the lender whether the loan is covered by a guarantee scheme and what security, if any, it requires from you.' },
    ],
  },
  {
    id: 'compare',
    n: '03',
    title: 'What should you compare before choosing a loan?',
    desc: 'The interest rate is only one part of the cost.',
    blocks: [
      { t: 'p', text: 'Compare the total cost and the conditions, not just the maximum loan amount or the first EMI shown in an advertisement.' },
      { t: 'ul', items: [
        { lead: 'Interest:', text: 'fixed or floating, benchmark, spread, reset frequency and APR where disclosed.' },
        { lead: 'Margin money:', text: 'the share of eligible costs you must contribute.' },
        { lead: 'Moratorium:', text: 'when principal repayment begins and whether interest accrues meanwhile.' },
        { lead: 'Repayment:', text: 'tenure, EMI, total amount repayable and prepayment conditions.' },
        { lead: 'Security:', text: 'collateral, guarantor and co-applicant requirements.' },
        { lead: 'Fees:', text: 'processing, legal, valuation, documentation and insurance charges.' },
        { lead: 'Coverage:', text: 'tuition, accommodation, living costs, travel, books, laptop and insurance.' },
        { lead: 'Disbursement:', text: 'when funds are released and whether fees are paid directly to the institution.' },
        { lead: 'Foreign exchange:', text: 'conversion rates and remittance charges for overseas payments.' },
      ] },
      { t: 'tip', text: 'Ask each lender for a written, like-for-like illustration using the same loan amount, course duration and repayment period.' },
    ],
  },
  {
    id: 'moratorium',
    n: '04',
    title: 'Does a moratorium mean you do not pay interest?',
    desc: 'What happens to interest while you study.',
    blocks: [
      { t: 'p', text: 'Usually, a moratorium postpones scheduled repayment of principal for a defined period. It does not necessarily stop interest from accruing. The exact treatment depends on the lender’s terms.' },
      { t: 'ul', items: [
        { text: 'Interest may accrue during the course and moratorium period.' },
        { text: 'If you do not service interest, the lender may add it to the outstanding principal in line with the agreement.' },
        { text: 'Capitalisation can increase the balance on which future interest and EMIs are calculated.' },
      ] },
      { t: 'p', text: 'Ask the lender for two repayment illustrations: one where you pay interest during study, and another where unpaid interest is added to the balance. Compare the total repayment in both cases.' },
      { t: 'warn', text: 'A lower EMI at the start does not necessarily mean a cheaper loan overall.' },
    ],
  },
  {
    id: 'international',
    n: '05',
    title: 'Can you borrow from an international education lender?',
    desc: 'What to check before comparing overseas providers.',
    blocks: [
      { t: 'p', text: 'Some international providers lend to eligible students studying at selected institutions and in selected destinations. Their products may be structured differently from Indian bank and NBFC loans.' },
      { t: 'ul', items: [
        { text: 'Check the lender’s legal entity and country of regulation.' },
        { text: 'Confirm whether the loan is denominated in INR or a foreign currency.' },
        { text: 'Understand the interest calculation, fees, repayment currency and exchange-rate risk.' },
        { text: 'Check whether a co-signer is required and who is legally responsible.' },
        { text: 'Confirm that your university, programme and intake are eligible.' },
      ] },
      { t: 'p', text: 'Examples to investigate include MPOWER Financing and Prodigy Finance. Availability is restricted to eligible schools, programmes and applicants; inclusion here is not an endorsement.' },
    ],
  },
  {
    id: 'government',
    n: '06',
    title: 'Which government portals and schemes should you know?',
    desc: 'Start with official sources, then confirm current eligibility.',
    blocks: [
      { t: 'p', lead: 'PM-Vidyalaxmi:', text: 'a government portal providing an application route for eligible students and participating lenders. Check the current scheme rules, institution eligibility and participating banks. Its collateral-free, guarantor-free loans are for students admitted to designated institutions in India, so check whether it covers your overseas course.' },
      { t: 'p', lead: 'Vidya Lakshmi:', text: 'an earlier education-loan application and tracking portal. Check the current government route and portal status before applying.' },
      { t: 'p', lead: 'CGFSEL:', text: 'a credit-guarantee arrangement for eligible education loans and lenders. It is not a grant to the student and does not automatically guarantee sanction or collateral-free terms.' },
      { t: 'tip', text: 'Always use official government pages for current scheme rules. Third-party summaries may be out of date.' },
      { t: 'link', href: SOURCES.pib, text: 'PM-Vidyalaxmi: Government of India (PIB) factsheet' },
    ],
  },
];

// The six starting points near the top of the page. The first four open a topic; the last two jump to the directory and the checklist.
export const cards = [
  ['01', 'Rules', 'What does RBI say?', 'Understand the role of RBI, banks and the IBA Model Education Loan Scheme.', '#s-rbi', 'Read the short guide'],
  ['02', 'Security', 'Do you need collateral?', 'Know the difference between collateral rules and credit-guarantee coverage.', '#s-collateral', 'Understand the thresholds'],
  ['03', 'Cost', 'What should you compare?', 'Check interest, fees, margin money, repayment and disbursement conditions.', '#s-compare', 'See the comparison list'],
  ['04', 'Repayment', 'What is a moratorium?', 'Learn why a repayment holiday does not necessarily mean interest-free borrowing.', '#s-moratorium', 'See how it works'],
  ['05', 'Lenders', 'Who offers education loans?', 'Explore public banks, private banks, NBFCs and international providers.', '#lenders', 'Browse the lender directory'],
  ['06', 'Ready', 'Are you ready to sign?', 'Use a practical checklist before accepting a sanction or signing an agreement.', '#checklist', 'Check your readiness'],
];

export const LENDER_TYPES = [
  ['all', 'All providers'],
  ['public', 'Public banks'],
  ['private', 'Private banks'],
  ['nbfc', 'NBFCs'],
  ['international', 'International'],
];
const TYPE_LABEL = { public: 'Public bank', private: 'Private bank', nbfc: 'NBFC', international: 'International' };
export const typeLabel = (t) => TYPE_LABEL[t];

export const lenders = [
  ['public', 'State Bank of India', 'Global Ed-Vantage. Confirm current overseas eligibility and security conditions.', 'https://sbi.co.in/'],
  ['public', 'Punjab National Bank', 'PNB Udaan. Verify product terms and eligible institutions.', 'https://www.pnbindia.in/'],
  ['public', 'Bank of Baroda', 'Baroda Education Loan. Check overseas course coverage.', 'https://www.bankofbaroda.in/'],
  ['public', 'Canara Bank', 'Education-loan schemes. Ask which current scheme applies to overseas study.', 'https://canarabank.com/'],
  ['public', 'Union Bank of India', 'Union Education Loan. Confirm overseas eligibility and current terms.', 'https://www.unionbankofindia.co.in/'],
  ['public', 'Indian Bank', 'Education-loan schemes. Confirm overseas course and institution eligibility.', 'https://indianbank.in/'],
  ['public', 'Bank of India', 'Star Education Loan. Check the latest overseas-study conditions.', 'https://bankofindia.co.in/'],
  ['public', 'Indian Overseas Bank', 'Education-loan schemes. Confirm current product naming and overseas coverage.', 'https://www.iob.in/'],
  ['public', 'Bank of Maharashtra', 'Education Loan Scheme. Ask about overseas programme eligibility.', 'https://bankofmaharashtra.in/'],
  ['public', 'Central Bank of India', 'Cent Vidyarthi. Verify current product and overseas eligibility.', 'https://www.centralbankofindia.co.in/'],
  ['public', 'UCO Bank', 'Education Loan Scheme. Confirm the latest terms with the bank.', 'https://www.ucobank.com/'],
  ['private', 'ICICI Bank', 'Education Loan. Check overseas eligibility, rates and fees.', 'https://www.icici.bank.in/'],
  ['private', 'Axis Bank', 'Education-loan offerings. Confirm current product name and overseas criteria.', 'https://www.axisbank.com/'],
  ['private', 'IDFC FIRST Bank', 'Abroad-study education loan offering. Verify current availability.', 'https://www.idfcfirstbank.com/'],
  ['private', 'Federal Bank', 'Education-loan offerings. Confirm overseas course and university coverage.', 'https://www.federalbank.co.in/'],
  ['private', 'YES BANK', 'Check current education-loan availability and whether lending is direct or partner-led.', 'https://www.yesbank.in/'],
  ['nbfc', 'HDFC Credila', 'Specialist education-finance provider. Check the legal lender and terms in the KFS.', 'https://www.credila.com/'],
  ['nbfc', 'Avanse Financial Services', 'Overseas education finance. Verify security, currency and university criteria.', 'https://www.avanse.com/'],
  ['nbfc', 'Auxilo Finserve', 'Education-focused lender. Confirm destination, course and applicant eligibility.', 'https://www.auxilo.com/'],
  ['nbfc', 'InCred Finance', 'Check overseas loan availability, eligible programmes and collateral conditions.', 'https://www.incred.com/'],
  ['nbfc', 'Tata Capital', 'Verify current overseas education products, limits and security requirements.', 'https://www.tatacapital.com/'],
  ['nbfc', 'Poonawalla Fincorp', 'Check current education-loan availability and institution eligibility.', 'https://www.poonawallafincorp.com/'],
  ['international', 'MPOWER Financing', 'Options for eligible students and schools, primarily in the USA and Canada. Check all conditions.', 'https://www.mpowerfinancing.com/'],
  ['international', 'Prodigy Finance', 'Financing for eligible students at selected schools and programmes.', 'https://prodigyfinance.com/'],
].map(([type, name, note, url]) => ({ type, name, note, url }));

export const official = [
  ['RBI: education-loan FAQs', 'Read the regulator’s FAQ and understand the banking framework.', SOURCES.rbi, 'Open RBI FAQs'],
  ['PM-Vidyalaxmi', 'Check the current government portal, eligible institutions and participating lenders.', SOURCES.pmv, 'Open portal'],
  ['Vidya Lakshmi', 'Check current status and the government’s latest route for education-loan applications.', SOURCES.vl, 'Open portal'],
];

export const checklist = [
  'I compared at least three lenders.',
  'I confirmed the actual interest rate and whether it is fixed or floating.',
  'I understand the benchmark, spread and rate-reset frequency.',
  'I understand collateral and guarantor requirements.',
  'I know the margin money and my family’s contribution.',
  'I calculated interest during study and moratorium.',
  'I know when the first EMI becomes payable.',
  'I checked repayment tenure and total repayment.',
  'I confirmed all processing, legal, valuation and insurance charges.',
  'I checked part-payment and foreclosure conditions.',
  'I confirmed which education and living expenses are covered.',
  'I understand disbursement timing and currency and remittance costs.',
  'My university, course and destination are eligible.',
  'I read the KFS, sanction letter and repayment schedule.',
  'My co-applicant understands their legal repayment responsibility.',
];
