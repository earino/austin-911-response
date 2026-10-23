#!/usr/bin/env python3
"""Portable static renderer, copied into each managed repo. Python stdlib only; no network."""
import argparse
import hashlib
import html
import json
from pathlib import Path
import re

VERSION = "2"

# Hand-drawn animated GIFs (data URIs): no scraped art, no network, no binaries.
GIF_B64 = {
    "globe": "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",
    "construction": "R0lGODlhlgAoAIEAAAAAAP//AP+lAAAAACH/C05FVFNDQVBFMi4wAwEAAAAh+QQADwAAACwAAAAAlgAoAAAI/wAFCBwoAIDBgwgTGiQ4UKFDhAwFPpwYseBEhxUvYoyoUWFFhh0TZgx5cCRJACZJpgy5suNHgicXcozZUmPNizcpzjyZESbNnSqBshTqkqhNozhnNvwJkqlPnkh1NoU6NehUiU6XUn1qlevQql+9Fq1qcavWrmfDph0r9ihYtmuzYjU7F21dtXfh5nXblm5Zu3/xBtY7mG/cpG/lFkbcV2rjhzkhR5Wc2G9MlJM3VnZ8mPNexp0FX46s+XHp0Kc/e158ubXr17Bjy55Nu7bt27hZ5t7Nu3ds1b6DC++dNsBB4wACIF+uHLnB5sqTN3c4HWH158uPR8c+Hfrx79qdQ/837lx6+e3lW3sVj/25+/fJE7K3Dj4+fPT36ee3z3/+/v7awafeeuDhx5996fl3YHb6GZheffNFqN9+CbZ3oFzyFRgfg+9VKOCDF2ZHXn0TStjhRCZqOKJuJQkl4YrnccfcdiTWKOKCNPZ3XYoK8YjghkO1+NaLP2rYYIxGqnjhggVyyCGTJzYIpFsyJWaigQCWmOF/ETqpZZRZQhlml3xhttmOFnoXXnQKmpdgjsyFt+WYcF73n3lHgkbacHz2SdhmfgYqqEgvATfooX72hJpHmTEKaGqsUWaao5MS2tSillYKUaOZYrrpo5R6KuRThoZaaqenfqrpqKJWuaqrZ0VvCulonKraqpmv4nrrnnrKaqqvqAJra6qsEgursb/SCmqwyubK67DCSrprrcVGe6y1uiL7rLTaUntts9MuC+1v3maL7bbfKgYussyq665l7wJGrrjVrntuueiaO6+z+PZLb7rwvpbvwP7y+6++IQUEACH5BAEPAAIALAsADACAAA8AgQAAAP+lAAAAAAAAAAj/AAUEGEgwgICDCBMqPFiQ4MKHCRsOhEhRokGKDy1izGhR4saFGj9G9CgSYciSAkmi1Kiy5EmXLUW+lBnzY8iGKBnW3DjT5k6MPXmqLCgAAEKjRZEqBWARgFOjT5EqZCrxaUKnB6U6bQrVatajOnFGhXoVa0qcJicWBZv0a9GmU9keheu27dq1dO/e1XqWqFy+WfOm/JtVaViiUusmptow8V7Dbz0C3ju36lW2iTVmvuyWrNGQjif3dRj6K9nRaidDRn2RM+XDBE8/BOyZbtTCZmGnjruW7EmtXu8Gpa3boOyFxD9LrtsZqW3etVvSNvzbNXXLx3m/1ixXMWu9qgNbRybcOe9iudztQgyuvPHi21q5Ts0tfDz5+mKDe//+OCf/lT9VFCBEQQE1IExoAZgggn4p2CCDDvkH0oETLkiThT5hKJSGDwUEACH5BAEPAAMALAsADACAAA8AgQAAAP//AP+lAAAAAAj/AAcAGEgQwICDCBMqPFiQ4MKHCRsOhEhRokGKDy1izGhR4saFGj9G9CgSYciSAkmi1Kiy5EmXLUW+lBnzY8iGKBnW3DjT5k6MPXmqLDggAEKjRZEqDcC0INOnSZk+fNoQ6lGlVwMQfCqV69GvKaka5GoU6UGrA5sCMJvyotmlZ89u3arwbd25acEmjVs0rFO9WOOmpQsY8Fata0cW3tu3qNOxdfU6xsu2sVTLGu3yfTuYMF/LERE3bcwwoeayfdf+Jf2ZLWKilbGiFvh6IunTRztfNA3WbGets6f27it6tdeobFUTZQ0a9WGtgK02Vo5Y+Gad1IlTxF1WN2jejHUncGYue/Lq1mex/t7tevjjxMEX4k7a+XZkwXjto6evfPx+zLpp9t9r1cG13WWpqXVcelBx5pR0DIKn1loIDsiQWGNBqF9aam1WmU845RQUUD9VVCJEI4p4IkchrrQiSC8qlKKLLcJUI003grgcjTtuFBAAIfkEAQ8AAgAsCwAMAIAADwCBAAAA/6UAAAAAAAAACP8ABQQYSDCAgIMIEyo8WJDgwocJGw6ESFGiQYoPLWLMaFHixoUaP0b0KBJhyJICSaLUqLLkSZctRb6UGfNjyIYoGdbcONPmTow9eaosKAAAQqNFkSoFYBGAU6NPkSpkKvFpQqcHpTptCtVq1qM6cUaFehVrSpwmJxYFm/Rr0aZT2R6F67bt2rV0797VepaoXL5Z86b8m1VpWKJS6yam2jDxXsNvPQLeO7fqVbaJNWa+7Jas0ZCOJ/d1GPor2dFqJ0NGfZEz5cMETz8E7Jlu1MJmYaeOu5bsSa1e7walrdug7IXEP0uu2xmpbd61W9I2/Ns1dcvHeb/WLFcxa72qA1tHJtw572K53O1CDK688eLbWrlOzS18PPn6YoN7//44J/+VP1UUIERBATUgTGgBmCCCfinYIIMO+QfSgRMuSJOFPmEolIYPBQQAIfkEAQ8AAwAsCwAMAIAADwCBAAAA//8A/6UAAAAACP8ABwAYSBDAgIMIEyo8WJDgwocJGw6ESFGiQYoPLWLMaFHixoUaP0b0KBJhyJICSaLUqLLkSZctRb6UGfNjyIYoGdbcONPmTow9eaosOCAAQqNFkSoNwLQg06dJmT582hDqUaVXAxB8KpXr0a8pqRrkahTpQasDmwIwm/Ki2aVnz27dqvBt3blpwSaNWzSsU71Y46alCxjwVq1rRxbe27eo07F19TrGy7axVMsa7fJ9O5gwX8sRETdtzDCh5rJ91/4l/ZktYqKVsaIW+Hoi6dNHO180DdZsZ62zp/buK3q116hsVRNlDRr1Ya2ArTZWjlj4Zp3UiVPEXVY3aN6MdSdwZi578urWZ7H+3u16+OPEwRfiTtr5dmTBeO2jp698/H7Mumn232vVwbXdZampdVx6UHHmlHQMgqfWWggOyJBYY0GoX1pqbVaZTzjlFBRQP1VUIkQjingiRyGutCJILyqUoostwlQjTTeCuByNO24UEAAh+QQBDwACACwLAAwAgAAPAIEAAAD/pQAAAAAAAAAI/wAFBBhIMICAgwgTKjxYkODChwkbDoRIUaJBig8tYsxoUeLGhRo/RvQoEmHIkgJJotSosuRJly1FvpQZ82PIhigZ1tw40+ZOjD15qiwoAABCo0WRKgVgEYBTo0+RKmQq8WlCpwelOm0K1WrWozpxRoV6FWtKnCYnFgWb9GvRplPZHoXrtu3atXTv3tV6lqhcvlnzpvybVWlYolLrJqbaMPFew289At47t+pVtok1Zr7slqzRkI4n93UY+ivZ0WonQ0Z9kTPlwwRPPwTsmW7UwmZhp467luxJrV7vBqWt26DshcQ/S67bGalt3rVb0jb82zV1y8d5v9YsVzFrvaoDW0cm3DnvYrnc7UIMrrzx4ttauU7NLXw8+fpig3v//jgn/5U/VRQgREEBNSBMaAGYIIJ+Kdgggw75B9KBEy5Ik4U+YSiUhg8FBAAh+QQBDwADACwLAAwAgAAPAIEAAAD//wD/pQAAAAAI/wAHABhIEMCAgwgTKjxYkODChwkbDoRIUaJBig8tYsxoUeLGhRo/RvQoEmHIkgJJotSosuRJly1FvpQZ82PIhigZ1tw40+ZOjD15qiw4IABCo0WRKg3AtCDTp0mZPnzaEOpRpVcDEHwqlevRrympGuRqFOlBqwObAjCb8qLZpWfPbt2q8G3duWnBJo1bNKxTvVjjpqULGPBWrWtHFt7bt6jTsXX1OsbLtrFUyxrt8n07mDBfyxERN23MMKHmsn3X/iX9mS1iopWxohb4eiLp00c7XzQN1mxnrbOn9u4rerXXqGxVE2UNGvVhrYCtNlaOWPhmndSJU8RdVjdo3ox1J3BmLnvy6tZnsf7e7Xr448TBF+JO2vl2ZMF47aOnr3z8fsy6afbfa9XBtd1lqal1XHpQceaUdAyCp9ZaCA7IkFhjQahfWmptVplPOOUUFFA/VVQiRCOKeCJHIa60IkgvKpSiiy3CVCNNN4K4HI07bhQQACH5BAEPAAIALAsADACAAA8AgQAAAP+lAAAAAAAAAAj/AAUEGEgwgICDCBMqPFiQ4MKHCRsOhEhRokGKDy1izGhR4saFGj9G9CgSYciSAkmi1Kiy5EmXLUW+lBnzY8iGKBnW3DjT5k6MPXmqLCgAAEKjRZEqBWARgFOjT5EqZCrxaUKnB6U6bQrVatajOnFGhXoVa0qcJicWBZv0a9GmU9keheu27dq1dO/e1XqWqFy+WfOm/JtVaViiUusmptow8V7Dbz0C3ju36lW2iTVmvuyWrNGQjif3dRj6K9nRaidDRn2RM+XDBE8/BOyZbtTCZmGnjruW7EmtXu8Gpa3boOyFxD9LrtsZqW3etVvSNvzbNXXLx3m/1ixXMWu9qgNbRybcOe9iudztQgyuvPHi21q5Ts0tfDz5+mKDe//+OCf/lT9VFCBEQQE1IExoAZgggn4p2CCDDvkH0oETLkiThT5hKJSGDwUEADs=",
    "flame": "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",
    "newbadge": "R0lGODlhNAAaAIEAAAAAAP///wD/AP//ACH/C05FVFNDQVBFMi4wAwEAAAAh+QQADAAAACwAAAAANAAaAAAI3AABCBxIsKDBggIOKlzIsCFBAQkhOpxI8WDChxUzTrwIYMBAjhpDfuQ4oORIkSJJllzpUSBIlA0lCmRJ8yNMhypp6nT58qbNmTqDtgTQE6bMjkKFnvSZMECAkk8HOJ0aVWrUqy5vXnQKtSvLq1eh/tQo06rXqmfDSjVJtOhClU/jel0pV23VsRsvrpVrlevev155phRYd25XsCzxhmza0S9aqIjZEvVJNABhsFPnciV8lHLOpCsVU24LFPRQt6M/1xQ8+u3AoKJbGzwamrVsnK9j33aNcXdGiZ1FBgQAIfkEAQwAAwAsCAAAACUAGgCBAAAA/wD//wAAAAAACM0ABwgcSLDgwAAGEypcSDAAQocMIzJE2FCixYoCBRy8KBFiRgEaBXrkaJDiAJAoQW4kedBkypcrSbp8STPkyI4Da+qMuXCkzp8tew4AAABkUQFEkx5FerSpyIQUiRqdmrJpU6M8PTKlupTrVaQqB0CcWbQsVZRmvy7dqDWt0aRT3VIVaVKsQLldwVpNyXMjgJNSwb4MHDikXYUB/g61Clfw1rs3Eef8CfPpRa2Uwx6WOblmUJaWT9LsC9qn5sigYxqum7pkQdatSz6EzTAgACH5BAEMAAQALAgAAAAlABoAgQAAAP///wD/////AAjNAAkIHEiw4EABBhMqXEhQAEKHDCMyRNhQosWKAgccvCgRYsYBGgV65GiQIgGQKEFuJHnQZMqXK0m6fEkz5MiOA2vqjLlwpM6fLXsSCBAAZNEBRJMeRXq0qciEFIkanZqyaVOjPD0ypbqU61WkKglAnFm0LFWUZr8u3ag1rdGkU91SFWlSrEC5XcFaTclzY4CTUsG+DBw4pF2FAv4OtQpX8Na7NxHn/Anz6UWtlMMeljm5ZlCWlk/S7Avap+bIoGMarpu6ZEHWrUs+hM0wIAAh+QQBDAADACwIAAAAJQAaAIEAAAD//wD/AAAAAAAIzQAHCBxIsODAAAYTKlxIMABChwwjMkTYUKLFigIFHLwoEWJGARoFeuRokOIAkChBbiR50GTKlytJunxJM+TIjgNr6oy5cKTOny17DgAAAGRRAUSTHkV6tKnIhBSJGp2asmlTozw9MqW6lOtVpCoHQJxZtCxVlGa/Lt2oNa3RpFPdUhVpUqxAuV3BWk3JcyOAk1LBvgwcOKRdhQH+DrUKV/DWuzcR5/wJ8+lFrZTDHpY5uWZQlpZP0uwL2qfmyKBjGq6bumRB1q1LPoTNMCAAIfkEAQwABAAsCAAAACUAGgCBAAAA//////8A/wAACM0ACQgcSLDgwAEGEypcSHAAQocMIzJE2FCixYoCBRy8KBFiRgEaBXrkaJAiAZAoQW4kedBkypcrSbp8STPkyI4Da+qMuXCkzp8texIIEABkUQFEkx5FerSpyIQUiRqdmrJpU6M8PTKlupTrVaQqCUCcWbQsVZRmvy7dqDWt0aRT3VIVaVKsQLldwVpNyXNjgJNSwb4MHDikXYUD/g61Clfw1rs3Eef8CfPpRa2Uwx6WOblmUJaWT9LsC9qn5sigYxqum7pkQdatSz6EzTAgACH5BAEMAAMALAgAAAAlABoAgQAAAAD/AP8AAAAAAAjNAAcIHEiw4MAABhMqXEgwAEKHDCMyRNhQosWKAgUcvCgRYkYBGgV65GiQ4gCQKEFuJHnQZMqXK0m6fEkz5MiOA2vqjLlwpM6fLXsOAAAAZFEBRJMeRXq0qciEFIkanZqyaVOjPD0ypbqU61WkKgdAnFm0LFWUZr8u3ag1rdGkU91SFWlSrEC5XcFaTclzI4CTUsG+DBw4pF2FAf4OtQpX8Na7NxHn/Anz6UWtlMMeljm5ZlCWlk/S7Avap+bIoGMarpu6ZEHWrUs+hM0wIAA7",
    "donebadge": "R0lGODlhYAAWAIEAAP//////AACAAAAAACH/C05FVFNDQVBFMi4wAwEAAAAh+QQARgAAACwAAAAAYAAWAAAI/wADCBxIsKDBgwgTKlzIsKFBARAjSpxIsaLFixgzatwYUSDHjyBDiuTocaTJkygzlkzJsqXJlRsBuJzJEmZGADhp6hxpE2POiDhlQgw69KfQiUQlJi0KVGjQo0eLEn0qE0AAjktzaq1aVUBXilCBimVKNqxXpBWhXtX4dOzZsF2jDlU6l65XqE7HypVb1+tan1rdfn271C5au3HPKla8Ny3Qv27LCl4ctW3ky3kT3/25WGrlx0g5JzX7dvLgznkRl05tuK9hq2C3kt56tzbjzpQnzzXqujdfypCbFq4sWrTU0JyP663Ll+pm40ODe95JHWVP5dWzg7zeW7t3jNy/ixPfGH68eYvlz6vv6LC9+/fw3QcEACH5BAEjAAQALBoAAgAFABEAgf///wD/AP//AACAAAgeAAMQGEhAIMGCBw0OVIgwoUOCDBk2XPiQYsWJBQMCACH5BAEjAAMALBoAAgAFABEAgf//////AACAAAAAAAgfAAUMGDhAIMGCBw0OVIjwIICEEAkybLjQYUSJFwsGBAA7",
    "starfield": "R0lGODlhQABAAIIAAAAAAP////8A/wD/////AAAAAAAAAAAAACH/C05FVFNDQVBFMi4wAwEAAAAh+QQAFAAAACwAAAAAQABAAAAIfgABCBxIsKDBgwgTKlzIsKHDhxAjSpxIsaLFixgzatzIsaPHjyBDihxJsqTJkyhTqvQoQMDKlzAjEohJs6bNgQRmTtR5s6dPlQF+Ch1KtKjRo0iTKn3Ic+lGAi2dSp1KtWrIAVazat3KtatGl17Dih1LNmvUsmjTql3Ltu3NgAAh+QQBFAAEACwGAAoAOgAxAIEAAAD/////AP///wAIagAJCBxIIADBgwgTKlzIsKHDhxAjSpxIsaLFixgVAgCQsaPHjyAdciQgIKTJkyhTqlzJsqXLlzBjypxJs6bNmzhz6tzJM+bGnkCDCh1KFOHIokiTKl3KNOfRplCjSp1K1ejTqlizshzAMiAAIfkEARQABAAsBgAKADoALQCBAAAA/wD/AP////8ACG4ACQgcSAAAwYMIEypcyLChw4cQI0qcSLGixYsYFQYIkLGjx48gHQ4QaDCkyZMoU14EUNJhS5UwY8qcWZCmzZs4c+rcybOnz59AIb4MChLARqJIkypdytShgKZQo0qdSpUpx6pYs2rdyhXi0aUBAQAh+QQBFAAEACwGAAoAOgAxAIEAAAD/////AP///wAIcAAJCBxIIADBgwgTKlzIsKHDhxAjSpxIsaLFixgzatzIsSNGAAIFeBxJsqRJjAMGQFR5sqXLlzAHGoxJs6bNmzhz6tzJs6fPhyx/jgwqtKjRo0iTNgSptKnTp1CjSp1KtarVq1gFAmCatatXmFxNBgQAIfkEARQABQAsBgAOADoALQCCAAAA/////wD/AP////8AAAAAAAAAAAAACGkACwgcSLCgwYMDAQBAyLChw4cQI0qcSPEhgYoYM2rcyLGjx4QLP4ocSbKkyY0hT6pcybKly5cwY8qcSbNmzJQ2VSrEmbOnz59Ag74cILSo0aNIkyodyXOp06dQo0pdKUDA1KtYjV5cGRAAIfkEARQABQAsBwAKADkAMQCCAAAA/////wD/AP////8AAAAAAAAAAAAACGwACwgcCGCgwYMIEypcyLChw4cQI0qcSLGixYsYCwgQkLGjx48gHxYMSbKkyZMUCRAQibKly5cwCwSISbOmzZs4c+rcybOnz4Mrf4YksFGo0aNIkypdyrSp06dQl3KMSrWq1atYs2rdunMkyoAAIfkEARQABAAsBgAKADoAMQCBAAAA/////wD///8ACGoACQgcSCAAwYMIEypcyLChw4cQI0qcSLGixYsYFQIAkLGjx48gHXIkICCkyZMoU6o8OGCly5cwY8qcSbOmzZs4c+rcybOnz59AgwodSrTmyKJIkypdynTn0aZQo0qdShXhxqpYs8psuTIgACH5BAEUAAUALAYADgA6ACkAggAAAP////8A/wD/////AAAAAAAAAAAAAAhmAAsIHEiwoMGDAwUIQMiwocOHECNKnEjxIYGKGDNq3Mixo8eBAABEFPmxpMmTKFMeJKmypcuXMGPKnEmzps2bOGmyzNky5E6eQIMKHUpU5oCiSJMqXcq0qcmFTqNKnUq1qkyFSwMCADs=",
    "counter": "R0lGODlhTQAPAIEAAAAAAP8A/4CAgB4eHiH/C05FVFNDQVBFMi4wAwEAAAAsAAAAAE0ADwAACPUAAQgcSLCgwYMIEypcyFCAw4cQI0qcSLGixYsWAQgYwLFjR4ceQ4IM+XEjSY4jT6YkuTKkxpMoTaqUyZKmSJseW+bE2fElxwBAS3YEGkCox6IxhyJN+nPpgJFEdw4gGpSjz6BVoRbNSrPqU5NIl0KdKnWpWJtLrw5lapYp2bMh4a41OvfrUY9qf7Kdm3IrXb1uydL1arfugLyCxwJWLBdwYKctGzs9DJZv5cUbqXI1XNix3bZuJ1/dilTr1NJojU7uLDgp6MKrfZ6W7DWyUM1/IYMlrBgvz8A3YbIODlPnX5e/h0stntw48OUnNWKcTr269YgBAQA7",
    "email": "R0lGODlhHAAQAIEAAAAAAAD/AP//AAAAACH/C05FVFNDQVBFMi4wAwEAAAAh+QQADAAAACwAAAAAHAAQAAAIaQABCBxIsKDBgwgTKhwooKHDhxAjNizocCHBABgnEhQgUGPCjBwDcNy4ceRBkRgDAFBJkqLJgSgFqmTJEKHGhjNlrqSoUGNOljQ7WtSJcaVInkN3tqyZ1GjRlwCgNo3qUqLViFOzakUYEAAh+QQBDAADACwCAAIAGQAMAIEAAAAA/wD//wAAAAAIZgABABhAsKDBgwgFCBA4QCHChwwDBFA4cCEAhw8HCJRIcWJFggIxHmQoYEAAggE+FgxZcmXFlAVhtjTIkiXKgTcbZqx5EKbMjDRBngTAUSVQkCZXNjR6VCNOiUt1NoW4FOfUhwoDAgAh+QQBDAADACwEAAIAGAAMAIEAAAAA/wD//wAAAAAIYAABDBhIsKDBgwMECEyIEOHCAAkBCBggcGJDigMgKgyg0CJGjwYBcBwYQKTEkAwLihQA0WRJkAQrfizZkubJhjJdiqT48qLKkhkFcrzpc+DOmB2LqiT4kqjSkAqfXhQQEAAh+QQBDAADACwEAAIAGAAMAIEAAAAA/wD//wAAAAAIXgAFDBhIsKDBgwMACEyIEGGAgQIVAhgQseHAhxEDCJBIsKJDAQ8TBuBY0CNBjSMHjBy5EWFFgSsnxmzZsGLMlCwnWjwJ4GFPiiR3XtQJMahQlQQl0jx6cONCpggBBAQAIfkEAQwAAwAsAgACABkADACBAAAAAP8A//8AAAAACGgABQgYQLCgwYMIAQAQOEAhwocBAgwQqHDgQgEOHw6ISDEAxoUNCVIEAHGgRJINLRocadBjQwASCYJEufKjwAAoYRacqXFkzJ0nVWosGBPnRpshhxJNOjElU6UbY84UChWhRYZVNSoMCAAh+QQBDAADACwAAAIAGQAMAIEAAAAA/wD//wAAAAAIaAAFCBhAsKDBgwgBABA4QCHChwECDBCocOBCAQ4fDohIMQDGhQ0JUgQAcaBEkg0tGhxp0GNDABIJgkS58qPAAChhFpypcWTMnSdVaiwYE+dGmyGHEk06MSVTpRtjzhQKFaFFhlU1KgwIACH5BAEMAAMALAAAAgAXAAwAgQAAAAD/AP//AAAAAAhZAAcIHEiwoMEBAAQmPGgwgEABCBNCXMjQ4cQAAgBQnFhRgEOEATQW5EgQY8gBIUNSJMgRYsqEL1eORIgSwMuaMivaBDkgY06dLEUybDgQgM+hSHv+TEoQQEAAIfkEAQwAAwAsAAACABcADACBAAAAAP8A//8AAAAACFkABwgcSLCgwQECBCY8aBCAwAAIEzpcyNAhRAEAAgigOLGixocZKQrsSDAkxIwhD3acGCDjAJQfKyJ82bImTZEMaVq0uDFnQZcDAfT0WXJgy6FEVeJMWlBAQAA7",
    "rainbow": "R0lGODlhLAEGAIIAAAAAAAD/AP8A/wD/////AP8AAAAA//+lACH/C05FVFNDQVBFMi4wAwEAAAAsAAAAACwBBgAACNwACwgcSLCgwYMIDR5YyLChw4cQIz4kQLGixYsYM2rEGKCjx48gQ4ocGXKAyZMoU6pcyVKlgZcwY8qcSbPmTAE4c+rcybOnz54AggZNSLSoUYlIkyrdyLSpU5JQo0ptSbWqVZtYs2r9ybWrVwFChxodS1ag0rNoGTpdy7ai1LdwPVqdS/ek1rt4YX7dyxds2LKAi6YdnLSt4aZxE0ety7hq3sdZ+0rmGhZA4MsHCWuGeLhzRsWgRTYevRKyaZqTU/OsjLn1wM2w1XqeTTG0bbmkc5s8zVuv6t9+hQYEADs=",
    "bullet": "R0lGODlhCgAKAIEAAAAAAAD/AAAAAAAAACH/C05FVFNDQVBFMi4wAwEAAAAh+QQADwAAACwAAAAACgAKAAAIHwABCBxIsKDBgQECHEyYsCBDhgQfNowI0eDEgxgPBgQAIfkEAQ8AAgAsAQABAAgACACBAAAA/wD/AAAAAAAACBkABQgIQDCAwIEFCSJMyLChw4cLCx5MKDAgACH5BAEPAAIALAAAAAAKAAoAgQAAAAD//wAAAAAAAAggAAUIDEAwgMCDBQsiTKiQocOHECMyFABxYcKDAxUKDAgAIfkEAQ8AAgAsAAAAAAoACgCBAAAA//8AAAAAAAAACBgABQQYSHCgwIIIEypcyLChw4cKDyYUEBAAOw==",
}


def gif_uri(name):
    return "data:image/gif;base64," + GIF_B64[name]



def canonical(value):
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n"


def esc(value):
    return html.escape(str(value), quote=True)


def link(url, label):
    if not url.startswith("https://"):
        raise ValueError("External links must be HTTPS")
    return f'<a href="{esc(url)}">{esc(label)}</a>'


def document(title, body, config, preview=False):
    """Retro shell: one window, one marquee, one hit counter. Content stays plain HTML tables."""
    notice = ('<div class="blink previewline">&#9888; REVIEW BUILD &#183; NOT PUBLISHED '
              '&#183; DO NOT LINK &#9888;</div>') if preview else ""
    star, globe, flame = gif_uri("starfield"), gif_uri("globe"), gif_uri("flame")
    rainbow, counter, mail = gif_uri("rainbow"), gif_uri("counter"), gif_uri("email")
    bullet = gif_uri("bullet")
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)} · {esc(config['title'])}</title><style>
body{{margin:0;padding:14px 8px;background:#000 url({star}) repeat;color:#fff;font:16px/1.55 "Times New Roman",Times,serif}}
.win{{max-width:920px;margin:0 auto;background:#c0c0c0;border:3px outset #f4f4f4;padding:3px}}
.titlebar{{background:#000080;color:#fff;font:bold 14px "Comic Sans MS","Comic Neue",cursive;padding:5px 10px;display:flex;justify-content:space-between;align-items:center;gap:10px}}
.titlebar a{{color:#ff0}}
.marq{{display:block;background:#000;color:#0f0;font:bold 14px "Courier New",monospace;padding:4px 0;white-space:nowrap;overflow:hidden}}
.content{{background:#fff;color:#000;padding:16px 18px;border:2px inset #f4f4f4}}
.content a{{color:#0000ee}}.content a:visited{{color:#551a8b}}
h1{{font:900 30px/1.15 Impact,"Comic Sans MS",cursive;margin:8px 0 10px;color:#000080}}
h2{{font:bold 21px "Comic Sans MS","Comic Neue",cursive;color:#000080;border-bottom:3px double #000080;margin:30px 0 12px;padding-bottom:3px}}
h3{{font:bold 16px "Comic Sans MS",cursive;margin:18px 0 8px}}
p{{max-width:78ch;overflow-wrap:anywhere}}
img{{image-rendering:pixelated}}
table{{border-collapse:collapse;border:3px outset #808080;background:#fff;margin:10px 0;width:100%}}
th{{background:#000080;color:#ff0;font:bold 13px "Courier New",monospace;padding:6px 9px;text-align:left;border:1px solid #808080}}
td{{border:1px solid #808080;padding:6px 9px;font:13px/1.5 "Courier New",monospace;vertical-align:top;overflow-wrap:anywhere}}
tr:nth-child(even) td{{background:#eef3ff}}
.rainbow{{width:100%;height:6px;display:block;margin:6px 0}}
pre{{background:#000;color:#0f0;font:13px/1.5 "Courier New",monospace;padding:12px;border:3px inset #808080;overflow-x:auto}}
code{{font-family:"Courier New",monospace}}
.blink{{animation:blink 1.1s steps(1) infinite}}
@keyframes blink{{50%{{visibility:hidden}}}}
.newbadge{{vertical-align:middle;margin-left:8px}}
.getbar td{{background:#fff;font:bold 14px "Comic Sans MS",cursive}}
.getbar td a{{max-width:100%}}
.getbar td a{{text-decoration:none;padding:4px 6px;border:2px outset #c0c0c0;background:#c0c0c0;color:#000;display:inline-block}}
.badges{{margin-top:10px}}
.badge{{display:inline-block;border:2px outset #fff;background:#c0c0c0;font:bold 10px "Courier New",monospace;color:#000;padding:3px 7px;margin:3px 4px 3px 0}}
.footer{{background:#c0c0c0;color:#000;font:13px/1.6 "Times New Roman",serif;padding:12px 16px;border:2px inset #f4f4f4;text-align:center}}
.footer a{{color:#0000ee}}
.counter{{image-rendering:pixelated}}
.note{{font-size:14px;color:#333}}
.tscroll{{overflow-x:auto}}
@media(max-width:640px){{.content{{padding:10px}}h1{{font-size:24px}}h2{{font-size:18px}}}}
</style></head><body>
{notice}
<div class="win">
<div class="titlebar"><span>{link(config['catalog_url'], config['title'])}</span><span>&#9733; EST. 2026 &#183; BEST AT 800&times;600 &#9733;</span></div>
<marquee class="marq" scrollamount="4">&#9733; WELCOME TO THE DATASET FACTORY &#9733; PUBLIC DATA &#8594; CHECKED BUILDS &#8594; HONEST BASELINES &#9733; NO POP-UPS &#9733; NO COOKIES &#9733; NO TRACKERS &#9733; HAND-MADE HTML &#9733; UNDER CONSTRUCTION SINCE THE NINETIES &#9733;</marquee>
<div class="content">
{body}
</div>
<img class="rainbow" src="{rainbow}" alt="">
<div class="footer">
<img class="counter" src="{counter}" alt="hit counter" width="77" height="15">
<p>You are visitor number <strong>0042137</strong>. Thank you for riding the information superhighway to our page.</p>
<div class="badges">
<span class="badge">NETSCAPE NOW!</span><span class="badge">Y2K COMPLIANT</span><span class="badge">MADE WITH NOTEPAD</span><span class="badge">100% HAND-SCRATCHED HTML</span><span class="badge">NO JAVA APPLET REQUIRED</span><span class="badge"><span class="blink">NEW!</span> LINK FREE</span>
</div>
<p class="webring">&#171; <a href="{esc(config['catalog_url'])}">prev site</a> &#183; <a href="{esc(config['catalog_url'])}">random</a> &#183; <a href="{esc(config['catalog_url'])}">next site</a> &#187; &nbsp;The Prediction Task WebRing</p>
<p><img src="{mail}" width="28" height="16" alt="e-mail"> Questions? <a href="https://github.com/earino">message the webmaster</a>. <a href="https://github.com/earino/dataset-factory-site/issues">Sign the guestbook</a>.</p>
<p class="note">Sources, construction and measured baselines accompany every dataset. Public holdouts stay outside evaluated agents&#8217; workspaces.</p>
<p class="note">Best viewed in Netscape Navigator 4.0 at 800&times;600. Also fine in your browser. &#169; The Dataset Factory &#183; <span class="blink">&#9733;</span> under construction &#9733; forever <span class="blink">&#9733;</span></p>
</div>
</div>
</body></html>'''
def navigation(record):
    """The get-it bar: the three canonical destinations for this release."""
    u = record["urls"]
    cells = "".join("<td>" + link(u[key], title) + "</td>" for key, title in (
        ("github_release", "&#128194; GitHub release"), ("huggingface_version", "&#129302; Hugging Face"),
        ("catalog", "&#128218; All datasets")))
    return '<div class="tscroll"><table class="getbar" aria-label="Dataset destinations"><tr>' + cells + "</tr></table></div>"


def dataset_body(r):
    """Inverted pyramid: what it is, how to get it, what is inside, then the fine print."""
    rows = sum(s["rows"] for s in r["splits"].values())
    split_rows = "".join(f'<tr><th scope="row">{esc(k)}</th><td>{s["rows"]:,}</td><td>' +
                         (f'{s["positives"]:,} ({s["positives"]/s["rows"]:.2%})' if "positives" in s else "&mdash;") +
                         '</td></tr>' for k, s in r["splits"].items())
    asset_rows = "".join(f'<tr><td>{link(a["download"], name)}</td><td>{a["bytes"]:,}</td>'
                         f'<td><code>{esc(a["sha256"])}</code></td></tr>' for name, a in r["assets"].items())
    terms = r["licenses"]
    docs = "".join(link(r["urls"]["github"] + '/blob/' + r["release_tag"] + '/' + path, label) for path, label in (
        ("DATA_DICTIONARY.md", "Data dictionary"), ("REPRODUCE.md", "Reproduction"),
        ("VERIFICATION.md", "Verification"), ("LICENSE.md", "Licence and attribution")))
    # The loading command is generated, not written into the template: a dataset with more than one
    # config (one per level) has to name it, or the command a reader copies raises "Config name is
    # missing". The names come from the record, which derives them from the same rule as the Hub card.
    configs = r.get("configs") or []
    snippet = "from datasets import load_dataset"
    if 0 < len(configs) <= 5:
        snippet += "".join("\nds = load_dataset(%r, %r, revision=%r)"
                           % (r["hf_repository"], name, r["release_tag"]) for name in configs)
    elif configs:
        # A per-target dataset has dozens of configs; one command per config made `bundle.json`
        # exceed the 256 KiB metadata cap. Name one, say how many there are, and where the rest are.
        snippet += ("\nds = load_dataset(%r, %r, revision=%r)"
                    % (r["hf_repository"], configs[0], r["release_tag"]))
        snippet += ("\n# %d configs, one per target: substitute any other name from README.md"
                    % len(configs))
    else:
        snippet += "\nds = load_dataset(%r, revision=%r)" % (r["hf_repository"], r["release_tag"])
    facts = "".join(f'<tr><th scope="row">{esc(k)}</th><td>{esc(v)}</td></tr>' for k, v in (
        ("Question", r["summary"]), ("Field", r["domain"] + " / " + r["task_type"]),
        ("Rows", f"{rows:,}"), ("Documented splits", str(len(r["splits"]))),
        ("This version", r["release_tag"]), ("Released", r["release_date"])))
    metrics = "".join(f'<tr><th scope="row">{esc(k)}</th><td>{esc(v)}</td></tr>'
                      for k, v in r["baseline"]["metrics"].items())
    return f'''<h1>{esc(r['title'])}</h1>
<p class="intro">{esc(r['summary'])}</p>
<p><img src="{gif_uri("donebadge")}" width="96" height="22" alt="released and complete"> <strong>This release is finished.</strong> Every number below is measured and reproducible.</p>
<h2>At a glance</h2><div class="tscroll"><table><tbody>{facts}{metrics}<tr><th scope="row">Artifact</th><td><code>{esc(r['artifact_version'])}</code></td></tr></tbody></table></div>
<h2>Get this dataset</h2>{navigation(r)}
<h3>How to load it</h3><pre><code>{esc(snippet)}</code></pre>
<p>The version links and checksums identify this artifact. Exclude the labelled holdout from the agent's workspace when running an evaluation.</p>
<h2>What is inside</h2>
<div class="tscroll"><table><thead><tr><th>Split</th><th>Rows</th><th>Positive labels</th></tr></thead><tbody>{split_rows}</tbody></table></div>
<h2>Files and checksums</h2>
<div class="tscroll"><table><thead><tr><th>Download</th><th>Bytes</th><th>SHA-256</th></tr></thead><tbody>{asset_rows}</tbody></table></div>
<h2>Release notes &#183; {esc(r['release_date'])}</h2>{''.join('<p>'+esc(p)+'</p>' for p in r['post']['paragraphs'])}
<h2>Why you can trust it</h2><p>{esc(r['qualification']['result'])} Gate {esc(r['qualification']['gate_version'])}.</p><p>{esc(r['baseline']['scope'])}</p>
<nav aria-label="Documentation">{docs}</nav>
<h2>Limits</h2><ul>{''.join('<li>'+esc(p)+'</li>' for p in r['limitations'])}</ul>
<h2>Source, licences, and citation</h2><p>{link(r['source']['url'],r['source']['name'])}</p><p>{esc(terms['attribution'])}</p>
<p>Source: {esc(terms['source_data'])}. Compilation: {esc(terms['data_compilation'])}. Code and documentation: {esc(terms['code'])}.</p>
<p>{esc(terms['compilation_scope'])}</p><h3>Suggested citation</h3><p>{esc(terms['citation'])}</p>'''
def render(config, records, preview=False, editions=()):
    """Pure rendering: no filesystem, clock, credentials, remote requests or private metadata."""
    if config.get("schema_version") != 1 or config.get("kind") not in ("catalog", "dataset"):
        raise ValueError("Unsupported renderer configuration")
    records = sorted(records, key=lambda r: (r["release_date"], r["release_tag"], r["dataset"]), reverse=True)
    seen = set()
    for r in records:
        copy = dict(r)
        checksum = copy.pop("record_sha256", None)
        if r.get("schema_version") != 1 or checksum != hashlib.sha256(canonical(copy).encode()).hexdigest():
            raise ValueError("Release record digest or schema does not match")
        if type(r.get("site_revision")) is not int or r["site_revision"] < 1:
            raise ValueError("Website edition must be a positive integer")
        for value in (r["dataset"], r["release_tag"]):
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}", value):
                raise ValueError("Unsafe dataset or version path")
        key = (r["dataset"], r["release_tag"])
        if key in seen:
            raise ValueError("Duplicate release record")
        seen.add(key)
    if not records:
        raise ValueError("A website needs at least one approved release record")
    files = {".nojekyll": ""}
    if config["kind"] == "dataset":
        if len({r["dataset"] for r in records}) != 1:
            raise ValueError("A dataset site may only contain one dataset")
        latest = records[0]
        history = '<h2>Versions</h2><ul>' + "".join('<li>' + link(r["urls"]["version"], r["release_tag"]) + '</li>' for r in records) + '</ul>'
        files["index.html"] = document(latest["title"], dataset_body(latest) + history, config, preview)
        files["release.json"] = canonical(latest)
        for r in records:
            prefix = 'versions/' + r["release_tag"] + '/'
            files[prefix + "index.html"] = document(r["title"], dataset_body(r) + history, config, preview)
            files[prefix + "release.json"] = canonical(r)
    else:
        latest = {}
        for r in records:
            latest.setdefault(r["dataset"], r)
        newest_date = max(r["release_date"] for r in records)
        card_rows = []
        for r in sorted(latest.values(), key=lambda r: r["release_date"], reverse=True):
            badge = (f'<img class="newbadge" src="{gif_uri("newbadge")}" width="52" height="26" alt="new!">'
                     if r["release_date"] == newest_date else "")
            rows = sum(s["rows"] for s in r["splits"].values())
            card_rows.append(
                f'<tr><th scope="row">{link(r["urls"]["version"], r["title"])}{badge}</th>'
                f'<td>{esc(r["domain"])}<br>{esc(r["task_type"])}</td>'
                f'<td>{rows:,}</td><td>{esc(r["release_date"])}</td>'
                f'<td>{esc(r["summary"])}</td></tr>')
        posts = []
        for r in records:
            url = config["catalog_url"] + 'releases/' + r["dataset"] + '/' + r["release_tag"] + '/'
            posts.append(f'<li>{esc(r["release_date"])} &#8212; {link(url,r["post"]["title"])}</li>')
            body = f'<h1>{esc(r["post"]["title"])}</h1>'
            body += '<p><img src="' + gif_uri("donebadge") + '" width="96" height="22" alt="released and complete"> ' + esc(r["summary"]) + '</p>'
            body += ''.join('<p>' + esc(p) + '</p>' for p in r["post"]["paragraphs"])
            body += navigation(r) + '<h2>Explore</h2>' + link(r["urls"]["version"], 'Open the dataset page')
            files[f'releases/{r["dataset"]}/{r["release_tag"]}/index.html'] = document(r["post"]["title"], body, config, preview)
        intro = f'''<h1><img src="{gif_uri("globe")}" width="36" height="36" alt="spinning globe"> The Dataset Factory</h1>
<p class="intro">{esc(config["description"])}</p>
<h2>What is this?</h2>
<p>The Dataset Factory turns public data into prediction tasks. Each dataset answers a real question. Each answer can be scored. You get the source, the build code, and a measured baseline. Your system tries to beat the baseline. Every release can be rebuilt and checked.</p>
<h2>How a dataset is made</h2>
<div class="tscroll"><table><tbody>
<tr><th scope="row">1 &#183; Find</th><td>Pick public data that contains a real question.</td></tr>
<tr><th scope="row">2 &#183; Check</th><td>Test the data before use. Row counts, splits, and licences must pass a fixed gate. A failed gate stops the release.</td></tr>
<tr><th scope="row">3 &#183; Build</th><td>One script builds the dataset from the source. The same input gives the same bytes.</td></tr>
<tr><th scope="row">4 &#183; Release</th><td>Publish with checksums, a measured baseline, and a labelled holdout. The holdout stays outside the evaluated workspace.</td></tr>
</tbody></table></div>
<h2>Use a dataset in three steps</h2>
<div class="tscroll"><table><tbody>
<tr><th scope="row">1 &#183; Load</th><td>Take the dataset from the GitHub release or the Hugging Face Hub.</td></tr>
<tr><th scope="row">2 &#183; Separate</th><td>Keep the labelled holdout out of your agent's workspace.</td></tr>
<tr><th scope="row">3 &#183; Score</th><td>Run the score script. Compare your number with the baseline.</td></tr>
</tbody></table></div>
<p>Who is it for? Teams that evaluate coding agents and prediction models. Anyone who needs honest, reproducible numbers.</p>
<h2><img src="{gif_uri("flame")}" width="16" height="24" alt=""> Datasets <img src="{gif_uri("flame")}" width="16" height="24" alt=""></h2>
<div class="tscroll"><table><thead><tr><th>Dataset</th><th>Field</th><th>Rows</th><th>Released</th><th>What it asks</th></tr></thead><tbody>{''.join(card_rows)}</tbody></table></div>
<h2>Release archive</h2><ul>{''.join(posts)}</ul>'''
        files["index.html"] = document(config["title"], intro, config, preview)
        files["catalog.json"] = canonical({"schema_version": 1, "releases": records})
    files["site-build.json"] = canonical({"renderer_version": VERSION, "preview": preview,
        "releases": [{key: r[key] for key in ("dataset", "release_tag", "artifact_version", "record_sha256")} for r in records]})
    for r in editions:
        base = (f'versions/{r["release_tag"]}/editions/' if config["kind"] == "dataset" else
                f'releases/{r["dataset"]}/{r["release_tag"]}/editions/') + str(r["site_revision"]) + '/'
        # Validate and render each immutable edition through the same contract.
        historical = render(config, [r], preview=preview)
        files[base + "release.json"] = canonical(r)
        files[base + "index.html"] = historical["index.html"]
    return files


def write_output(out, files):
    out = Path(out)
    marker = out / ".dataset-factory-site-output"
    if out.is_symlink() or any(p.is_symlink() for p in (out, *out.parents)):
        raise ValueError("Output path must not pass through a symlink")
    if out.exists() and (not out.is_dir() or ((out / '.git').exists()) or (any(out.iterdir()) and not marker.is_file())):
        raise ValueError("Refusing to overwrite a non-owned output directory")
    out.mkdir(parents=True, exist_ok=True)
    marker.write_text("dataset-factory site output v1\n")
    for relative, text in files.items():
        path = out / relative
        if path.is_symlink() or any(p.is_symlink() for p in path.parents):
            raise ValueError("Output contains a symlink")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--out", type=Path, default=Path("_site"))
    parser.add_argument("--preview", action="store_true")
    args = parser.parse_args()
    config = json.loads((args.source / "config.json").read_text())
    records = [json.loads(p.read_text()) for p in sorted((args.source / "records").glob("*/*.json"))]
    editions = [json.loads(p.read_text()) for p in sorted((args.source / "editions").glob("*/*/*.json"))]
    write_output(args.out, render(config, records, args.preview, editions))
    print(f"Rendered {len(records)} release(s) with renderer {VERSION}")


if __name__ == "__main__":
    main()
