import secrets
from typing import Dict, Iterable, List, Tuple, Union

from py_ecc.optimized_bn128 import curve_order as CURVE_ORDER
from py_ecc.optimized_bn128 import add, multiply, normalize
from py_ecc.optimized_bn128 import G1
from py_ecc.typing import Optimized_Point3D 
from py_ecc.fields import optimized_bn128_FQ, optimized_bn128_FQ2
from web3 import Web3

PointG1 = Optimized_Point3D[optimized_bn128_FQ]
PointG2 = Optimized_Point3D[optimized_bn128_FQ2]
FQ = optimized_bn128_FQ
keccak_256 = Web3.solidityKeccak


def symmetric_key_2D(master_pub_key, priv_key):
    from py_ecc.bn128 import multiply
    return multiply(master_pub_key, priv_key)[0]


def random_scalar() -> int:
    return secrets.randbelow(CURVE_ORDER)


def generate_keypair() -> Tuple[int, PointG1]:
    sk = random_scalar()
    pk = multiply(G1, sk) 
    return sk, pk


def generate_secret(a_pub_k, b_priv_k) -> PointG1:
    return multiply(a_pub_k, b_priv_k)


def symmetric_key(a_pub_k, b_priv_k) -> int:
    return int(normalize(generate_secret(a_pub_k, b_priv_k))[0])


def share_secret(
    secret: int, indices: List[int], threshold: int 
) -> Tuple[Dict[int, int], List[PointG1]]:
    """ Computes shares of a given secret such that at least threshold + 1 shares are required to 
        recover the secret. Additionally returns the commitents to the coefficient of the polynom
        used to verify the validity of the shares.
    """
    coefficients = [secret] + [random_scalar() for j in range(threshold)]

    def f(x: int) -> int:
        """ evaluation function for secret polynomial
        """
        return (
            sum(coef * pow(x, j, CURVE_ORDER) for j, coef in enumerate(coefficients)) % CURVE_ORDER
        )

    shares = {x: f(x) for x in indices}
    commitments = [multiply(G1, coef) for coef in coefficients]
    return shares, commitments


def verify_share(j: int, s_ij: int, Cik: List[PointG1]) -> bool:
    """ check share validity and return True if the share is valid, False otherwise
    """
    r = Cik[0]
    for k, c in enumerate(Cik[1:]):
        r = add(r, multiply(c, pow(j, k + 1, CURVE_ORDER)))
    return normalize(multiply(G1, s_ij)) == normalize(r)


def dleq(x1: PointG1, y1: PointG1, x2: PointG1, y2: PointG1, alpha: int) -> Tuple[int, int]:
    """ DLEQ... discrete logarithm equality
        Proofs that the caller knows alpha such that y1 = x1**alpha and y2 = x2**alpha
        without revealing alpha.
    """
    w = random_scalar()
    a1 = multiply(x1, w)
    a2 = multiply(x2, w)
    c = keccak_256(
        abi_types=["uint256"] * 12,
        values=[
            int(v)
            for v in normalize(a1)
            + normalize(a2)
            + normalize(x1)
            + normalize(y1)
            + normalize(x2)
            + normalize(y2)
        ],
    )
    c = int.from_bytes(c, "big")
    r = (w - alpha * c) % CURVE_ORDER
    return c, r


def dleq_verify(
    x1: PointG1, y1: PointG1, x2: PointG1, y2: PointG1, challenge: int, response: int
) -> bool:
    a1 = add(multiply(x1, response), multiply(y1, challenge))
    a2 = add(multiply(x2, response), multiply(y2, challenge))
    c = keccak_256(  # pylint: disable=E1120
        abi_types=["uint256"] * 12,  # 12,
        values=[
            int(v)
            for v in normalize(a1)
            + normalize(a2)
            + normalize(x1)
            + normalize(y1)
            + normalize(x2)
            + normalize(y2)
        ],
    )
    c = int.from_bytes(c, "big")
    return c == challenge


def sum_scalars(scalars: Iterable[int]):
    return sum(scalars) % CURVE_ORDER


def sum_points(points: Union[Iterable[PointG1], Iterable[PointG2]]):
    result = None
    for p in points:
        if result is None:
            result = p
        else:
            result = add(result, p)
    return result

