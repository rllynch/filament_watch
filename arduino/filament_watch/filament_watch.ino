#define IN1 2
#define IN2 3

int last_in1;
int last_in2;
int last_code;
int pos = 0;

int decode(int in1, int in2)
{
  return (in2 << 1) | (in1 ^ in2);
}

void isr_common(int cur_in1, int cur_in2)
{
  int cur_code = decode(cur_in1, cur_in2);
  
  if (cur_code != last_code)
  {
    if (((cur_code + 1) & 3) == last_code)
      pos++;
    if (((cur_code - 1) & 3) == last_code)
      pos--;
      
    //Serial.println(cur_code);
    //Serial.println(pos);
    
    last_code = cur_code;
  }

  last_in1 = cur_in1;
  last_in2 = cur_in2;
}

void isr1()
{
  int cur_in1 = digitalRead(IN1);
  int cur_in2 = last_in2;
  isr_common(cur_in1, cur_in2);
}

void isr2()
{
  int cur_in1 = last_in1;
  int cur_in2 = digitalRead(IN2);
  isr_common(cur_in1, cur_in2);
}

void setup() {
  // put your setup code here, to run once:
  pinMode(IN1, INPUT_PULLUP);           // set pin to input
  pinMode(IN2, INPUT_PULLUP);           // set pin to input
  Serial.begin(115200);
  
  last_in1 = digitalRead(IN1);
  last_in2 = digitalRead(IN2);
  last_code = decode(last_in1, last_in2);

  attachInterrupt(0, isr1, CHANGE);
  attachInterrupt(1, isr2, CHANGE);
}

void loop() {
  delay(1000);
  Serial.println(pos);
}

