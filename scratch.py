#Type hints: labels that say what kind of data goes in and out
def add(a:int,b:int):
    return a+b

#Lists and Dicts (APIs speak in these)
names:list[str]=["Asha","Ravi"]
names:dict[str,str]={"name":"Ravi","city":"Mumbai"}

#Loops and conditions
for n in names:
    if n.startswith("A"):
        print(f"{n} starts with A")

#Classes: a blueprint for an object
class Dog:
    def __init__(self,name:str):
        self.name=name

    def bark(self) -> str:
        return f"{self.name} says woof"

print(Dog("Bruno").bark())