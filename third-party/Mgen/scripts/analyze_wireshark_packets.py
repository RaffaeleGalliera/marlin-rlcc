import pandas as pd

df = pd.read_csv('1hour_225-300_55-100_2.csv')

#df.head()

#df[df['Protocol']=='TCP'].head()

#df.shape

#df[df['Protocol']=='TCP'].shape

#df[df['Protocol']=='UDP'].shape

dfTCP = df[df['Protocol']=='TCP']

dfUDP = df[df['Protocol']=='UDP']

totTime = df.iloc[-1,1]
#print(totTime)

totTimeOff = 0
for i in range(len(df)-1) :
  if (df.iloc[i+1,1]-df.iloc[i,1]) > 1:
    tStart = df.iloc[i,1]
    tEnd = df.iloc[i+1,1]
    tOff = tEnd - tStart
    totTimeOff = totTimeOff + tOff
    #print(df.iloc[i, 0], df.iloc[i, 1])
    #print(tOff)
#print(totTimeOff)

totTCPTimeOff = 0
for i in range(len(dfTCP)-1) :
  if (dfTCP.iloc[i+1,1]-dfTCP.iloc[i,1]) > 1:
    tStart = dfTCP.iloc[i,1]
    tEnd = dfTCP.iloc[i+1,1]
    tOff = tEnd - tStart
    totTCPTimeOff = totTCPTimeOff + tOff
    #print(df.iloc[i, 0], df.iloc[i, 1])
    #print(tOff)
#print(totTCPTimeOff)

totUDPTimeOff = 0
for i in range(len(dfUDP)-1) :
  if (dfUDP.iloc[i+1,1]-dfUDP.iloc[i,1]) > 1:
    tStart = dfUDP.iloc[i,1]
    tEnd = dfUDP.iloc[i+1,1]
    tOff = tEnd - tStart
    totUDPTimeOff = totUDPTimeOff + tOff
    #print(df.iloc[i, 0], df.iloc[i, 1])
    #print(tOff)
#print(totUDPTimeOff)

totUDPTimeOff = totUDPTimeOff- totTimeOff
totTCPTimeOff = totTCPTimeOff - totTimeOff
#print(totUDPTimeOff) 
#print(totTCPTimeOff)

percBothDown = (totTimeOff / totTime) * 100
percTCPDown = (totTCPTimeOff / totTime) * 100
percUDPDown = (totUDPTimeOff / totTime) * 100
print('percentage Both Down  = ', percBothDown)
print('percentage TCP Down  = ', percTCPDown)
print('percentage UDP Down  = ', percUDPDown)
