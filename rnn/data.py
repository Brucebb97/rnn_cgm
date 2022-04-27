import csv
import scipy
from scipy import io
features_struct = scipy.io.loadmat('./PARSED.mat')
print(features_struct.keys())
print(features_struct['cgm'][0])
cgm = features_struct['cgm'][0]
cgm = cgm[:7758]
bolus = features_struct['bolus'][0]
bolusDate= features_struct['bolusDate'][0]
cgmDate = features_struct['cgmDate'][0]
cgmDate = cgmDate[:7758]
mealOccurred = features_struct['mealOccurred'][0]
mealOccurred = mealOccurred[:7758]
print(len(cgm))
print(len(bolus))
print(len(bolusDate))
print(len(mealOccurred))
print(len(cgmDate))
data_list = []
for a,b,c,d,e in zip(bolus,bolusDate,mealOccurred,cgmDate, cgm):
    x = {}
    x['bolus']= a
    x['bolusDate']= b
    x['mealOccurred'] = c
    x['cgmDate'] = d
    x['cgm'] = e
    data_list.append(x)
#print(data_list)

with open("parsed.csv",'w',newline='',encoding='UTF-8') as f_c_csv:
    writer = csv.writer(f_c_csv)
    writer.writerow(['bolus', 'bolusDate','mealOccurred','cgmDate', 'cgm'])
    for nl in data_list:
        writer.writerow(nl.values())
print("写入完成！")