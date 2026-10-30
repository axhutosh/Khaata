"""Signals for telling a person from a business in a UPI payee name.

UPI narrations carry the payee name cut to its first ~8-10 characters (NPCI Circular 43),
so matching is by token prefix. Lists are hand-written common Indian names, not a dataset:
they only need to catch the frequent cases; the Review screen handles the rest.
"""

FIRST_NAMES = set("""
aarav aarti aarush aayush abhay abhijit abhilash abhinav abhishek aditi aditya ajay ajit akash
akhil akshay akshata alka alok aman amar amit amita amol amrita anand ananya anil anita anjali
anju ankit ankita ankur anoop anshu anshul anuj anupam anuradha anurag anushka aparna archana
arjun arpita arun aruna arvind asha ashish ashok ashwin atul avinash ayush babita babu balaji
bhagwan bharat bhavana bhavesh bhavna bhupesh bindu chandan chandra chetan chirag deepa deepak
deepika deepti devendra dhanraj dharmendra dhruv dilip dinesh divya durga ekta farhan fatima
ganesh gaurav gautam geeta girish gopal govind gurpreet hari harish harsh harsha hema hemant
himanshu indu ishaan ishita jagdish jai jatin jaya jayesh jitendra jyoti kajal kalpana kamal
kamala karan karthik kavita kavya keshav ketan kiran kishore komal krishna kunal kusum lakshmi
lalit lata laxmi madhu madhuri mahendra mahesh manish manisha manju manoj meena meenakshi megha
mehul mohan mohit mukesh murali nagesh naina naresh naveen navin neelam neha nikhil nikita nilesh
nisha nitin pallavi pankaj parth payal pooja poonam prabhu pradeep prakash pramod pranav prashant
prateek praveen preeti prem priya priyanka puja pushpa rachna radha raghav rahul raj raja rajan
rajat rajendra rajesh rajeev rajiv rakesh ram ramesh rani ranjit rashmi ravi rekha renu reshma
ritu rohan rohit roshan ruchi rupa sachin sagar sahil sai sakshi salim sameer sandeep sandhya
sangeeta sanjay sanjeev santosh sapna sarita satish saurabh savita seema shailesh shalini
shankar sharad shashi shekhar shilpa shiv shivani shobha shreya shubham shweta siddharth simran
sneha sonal sonia sonu srinivas subhash suman sumit sunil sunita suraj suresh surya sushil
sushma swati tanvi tarun tushar uday uma umesh usha vaibhav varsha varun vasant veena vijay
vikas vikram vimal vinay vineet vinod vipin vishal vivek yash yogesh zoya
abdul ahmed ali amjad anwar arif asif aziz faisal farooq feroz hamid hasan hussain imran irfan
iqbal javed kareem khalid mohammad mohammed mohd nadeem naseem nasir rafiq rahim rashid rizwan
sajid salman shahid shakeel sohail tariq wasim yusuf zubair ayesha nazia rubina salma shabana
shaheen shabnam
john joseph thomas mathew george james paul peter mary anthony francis jose antony xavier
balwinder harpreet jaspreet manpreet navjot paramjit sukhwinder kuldeep jasbir gurmeet
""".split())

SURNAMES = set("""
kumar kumari singh sharma verma gupta agarwal aggarwal agrawal jain bansal goel goyal mittal
garg patel shah mehta desai joshi trivedi pandya modi parikh reddy rao naidu nair menon pillai
iyer iyengar krishnan subramanian murthy gowda shetty hegde kamath pai bhat yadav mishra
tiwari pandey dubey shukla tripathi chaturvedi srivastava saxena mathur kapoor khanna malhotra
chopra arora bhatia sethi sood kohli chauhan rathore rajput thakur chaudhary choudhary
das dey roy ghosh bose sen mukherjee banerjee chatterjee chakraborty dutta basu sarkar paul
mondal biswas patil pawar jadhav shinde kulkarni deshpande gaikwad more kale naik sawant
khan sheikh shaikh ansari qureshi siddiqui syed mirza pathan
""".split())

TITLES = {"mr", "mrs", "ms", "miss", "smt", "shri", "shree", "dr", "kumari", "km"}

# words that only a business uses in its name
BUSINESS_WORDS = set("""
enterprises enterprise traders trading pvt private ltd limited llp inc corp corporation company co
services service solutions agency agencies industries industry associates international impex
exports imports store stores shop shoppe mart centre center emporium bhandar bhandaar depot
ventures technologies tech retail wholesale distributors suppliers sons brothers bros
and & infra builders developers motors automobiles electricals electronics hotel restaurant
cafe foods bakery sweets medical medicals pharmacy clinic hospital labs studio studios
academy institute classes school college garments textiles jewellers mall bazaar bazar
""".split())

# merchant-QR and gateway VPAs (the local part SBI keeps once it drops the @handle)
MERCHANT_VPA_HINTS = ("paytmqr", "paytm.s", "paytm-", "bharatpe", "gpay-", "rzp", "razorpay",
                      "pinelabs", "mswipe", "ezetap", "payu", "cashfree", "billdesk", "merchant",
                      "store", "shop", "upi.swiggy", "zomato", "phonepe.")


def _prefix_hit(token: str, names: set[str]) -> bool:
    if token in names:
        return True
    # truncated or run-together names ("rajeshkum", "priyanka s") still start with the name
    return any(len(n) >= 4 and token.startswith(n) for n in names)


def person_score(tokens: list[str]) -> float:
    score = 0.0
    if tokens and tokens[0] in TITLES:
        score += 2
        tokens = tokens[1:]
    if tokens and _prefix_hit(tokens[0], FIRST_NAMES):
        score += 2
    if any(t in SURNAMES for t in tokens[1:]) or (len(tokens) == 1 and tokens[0] in SURNAMES):
        score += 1
    return score
