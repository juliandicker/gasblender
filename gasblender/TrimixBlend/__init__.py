import logging
import json
import azure.functions as func

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')

    try:
        req_body = req.get_json()
    except ValueError:
        pass
    else:
        start_bar = req_body.get('start_bar')
        start_o2 = req_body.get('start_o2')
        start_he = req_body.get('start_he')
        finish_bar = req_body.get('finish_bar')
        finish_o2 = req_body.get('finish_o2')
        finish_he = req_body.get('finish_he')
        helium_bar = req_body.get('helium_bar')
        helium_o2 = req_body.get('helium_o2')
        helium_he = req_body.get('helium_he')

    if start_bar and start_o2 and start_he and finish_bar and finish_o2 and finish_he:
        start_gas = gas(start_bar, start_o2, start_he)
        finish_gas = gas(finish_bar, finish_o2, finish_he)

        if helium_bar and helium_o2 and helium_he:
            helium_gas = gas(helium_bar, helium_o2, helium_he)
        else:
            helium_gas = gas(250, 0, 100)

        result = trimix_blend(start_gas, finish_gas, helium_gas)

        return func.HttpResponse(result.toJSON())
    else:
        return func.HttpResponse(
             "This HTTP triggered function executed successfully. Pass parameters in the request body for a personalized response.",
             status_code=200
        )

class gas:
    def __init__(self, bar, o2, he):
        self.bar = bar
        self.o2 = o2
        self.he = he
        self.n2 = 100 - o2 - he
        self.bar_he = (self.bar + 1) * self.he / 100
        self.bar_o2 = (self.bar + 1) * self.o2 / 100
        self.bar_n2 = (self.bar + 1) * self.n2 / 100

    def __str__(self):
         return f"{self.bar:.1f} bar {self.short_name()}"

    def short_name(self):
        if self.o2 == 100:
            return "O2"
        elif self.he == 100:
            return "He"
        elif self.o2 == 21 and self.he == 0:
            return "Air"
        elif self.o2 > 21 and self.he == 0:
            return f"N{self.o2:.1f}%"
        else:
            return f"{self.o2:.1f}/{self.he:.1f}"

def topup_blend(start_gas, topup_gas, bar = None):
    bar = bar if bar != None else topup_gas.bar
    o2 = round((((start_gas.o2 / 100) * start_gas.bar) + ((topup_gas.bar - start_gas.bar) * (topup_gas.o2 / 100))) / topup_gas.bar * 100, 1)
    he = round((((start_gas.he / 100) * start_gas.bar) + ((topup_gas.bar - start_gas.bar) * (topup_gas.he / 100))) / topup_gas.bar * 100, 1)
    return gas(bar, o2, he)

class blend_step:
    def __init__(self, name, start_gas, result_gas):
        self.name = name
        self.start_gas = start_gas
        self.result_gas = result_gas
    
    def __str__(self):
        diff = self.result_gas.bar - self.start_gas.bar
        return f"{self.name}\t{self.start_gas.bar:.1f}\t{self.result_gas.bar:.1f} ({diff:.1f})\t{self.result_gas}"

class trimix_blend:
    def __init__(self, start_gas, finish_gas, he_gas = gas(300, 0, 100)):
        self.start_gas = start_gas
        self.finish_gas = finish_gas
        self.he_gas = he_gas
        self.blend()

    def __str__(self):
        msg = "\tStart\tFinish\t\tTest\n"
        for step in self.steps:
            msg += step.__str__() + "\n"
        return msg

    def toJSON(self):
        return json.dumps(self, default=lambda o: o.__dict__, sort_keys=True, indent=4)

    def blend(self):
        self.steps = []
        if self.finish_gas.he == 0:
            self.step_o2(self.start_gas)
        else:
            self.step_he(self.he_gas.short_name(), self.start_gas, self.he_gas)
            self.step_o2(self.steps[-1].result_gas)

        self.step_air()
    
    def step_he(self, name, start_gas, he_gas):
        bar_p = (self.finish_gas.bar_he - start_gas.bar_he) * (100 / he_gas.he)
        he_required = start_gas.bar + bar_p > he_gas.bar
        if he_required:
            bar_p = he_gas.bar - start_gas.bar

        target_he = start_gas.bar + bar_p
        self.add_step(name, start_gas, gas(round(target_he, 1), he_gas.o2, he_gas.he))

        if he_required:
            self.step_he("He", self.steps[-1].result_gas, gas(300, 0, 100))

    def step_o2(self, start_gas):
        target_o2 = start_gas.bar + self.finish_gas.bar_o2 - start_gas.bar_o2 - ((self.finish_gas.bar_n2 - start_gas.bar_n2) * (0.21 / 0.79))
        self.add_step("O2", start_gas, gas(round(target_o2, 1), 100, 0))

    def step_air(self):
        target_air = self.steps[-1].result_gas.bar + ((self.finish_gas.bar_n2 - self.steps[-1].result_gas.bar_n2) / 0.79)
        self.add_step("Air", self.steps[-1].result_gas, gas(round(target_air, 1), 21, 0))

    def add_step(self, name, start_gas, topup_gas):
        self.steps.append(blend_step(name, start_gas, topup_blend(start_gas, topup_gas)))