"""공정 데이터 계약 pydantic 스키마.

설계서(docs/design.md) 8.2절 구조를 따르되, 판정에 필요한 두 항목을 최소로 확장했다
(docs/progress.md의 "설계서 대비 단순화/확장 기록" 참고).

- ``sources[].sensor`` + 최상위 ``sensors``: FAB-T001이 "샘플링 주기가 다른 센서"를
  판정하려면 어떤 소스가 어떤 센서인지 알아야 하는데, 설계서 예시에는 이 정보가 없다.
- ``entities[].parent``: FAB-J001의 "공통 조상 입도" 계산에 쓴다. wafer는 설계서
  예시에 이미 ``parent: lot``이 있었고, metrology/step_event에도 동일한 방식으로
  명시했다.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Parameter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    family: str
    name_patterns: list[str] = Field(min_length=1)

    @field_validator("name_patterns")
    @classmethod
    def _no_blank_patterns(cls, v: list[str]) -> list[str]:
        if any(not p.strip() for p in v):
            raise ValueError("name_patterns에 빈 문자열은 허용하지 않는다")
        return v


class Entity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: list[str] = Field(min_length=1)
    grain: str
    parent: str | None = None
    time_window: tuple[str, str] | None = None
    sampling_period: str | None = None
    coverage: str | None = None

    @field_validator("key")
    @classmethod
    def _no_blank_keys(cls, v: list[str]) -> list[str]:
        if any(not k.strip() for k in v):
            raise ValueError("key에 빈 문자열은 허용하지 않는다")
        return v


class Relationship(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    from_: str = Field(alias="from")
    to: str
    cardinality: str
    coverage: str | None = None


class Source(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pattern: str
    entity: str
    sensor: str | None = None


class SensorSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sampling_period: str


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_version: str
    unit_families: dict[str, list[str]]
    parameters: dict[str, Parameter] = Field(default_factory=dict)
    entities: dict[str, Entity]
    relationships: list[Relationship] = Field(default_factory=list)
    sources: list[Source] = Field(default_factory=list)
    sensors: dict[str, SensorSpec] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _check_cross_references(self) -> "Contract":
        errors: list[str] = []

        for fam_name, tokens in self.unit_families.items():
            if not tokens:
                errors.append(f"unit_families.{fam_name}에 단위 토큰이 비어 있다")

        for param_name, param in self.parameters.items():
            if param.family not in self.unit_families:
                errors.append(
                    f"parameters.{param_name}.family={param.family!r}가 unit_families에 없다"
                )

        for entity_name, entity in self.entities.items():
            if entity.parent is None:
                continue
            if entity.parent not in self.entities:
                errors.append(
                    f"entities.{entity_name}.parent={entity.parent!r}가 entities에 없다"
                )
            elif entity.parent == entity_name:
                errors.append(f"entities.{entity_name}.parent가 자기 자신을 참조한다")

        for entity_name in self.entities:
            seen = {entity_name}
            current = self.entities[entity_name].parent
            while current is not None and current in self.entities:
                if current in seen:
                    errors.append(f"entities.{entity_name}의 parent 체인에 순환이 있다")
                    break
                seen.add(current)
                current = self.entities[current].parent

        for idx, rel in enumerate(self.relationships):
            if rel.from_ not in self.entities:
                errors.append(f"relationships[{idx}].from={rel.from_!r}가 entities에 없다")
            if rel.to not in self.entities:
                errors.append(f"relationships[{idx}].to={rel.to!r}가 entities에 없다")

        for idx, source in enumerate(self.sources):
            if source.entity not in self.entities:
                errors.append(f"sources[{idx}].entity={source.entity!r}가 entities에 없다")
            if source.sensor is not None and source.sensor not in self.sensors:
                errors.append(f"sources[{idx}].sensor={source.sensor!r}가 sensors에 없다")

        if errors:
            raise ValueError("; ".join(errors))
        return self

    def ancestors(self, entity_name: str) -> list[str]:
        """entity_name에서 parent 체인을 따라 올라간 목록 (자기 자신 포함, 가까운 순)."""
        chain = [entity_name]
        current = self.entities[entity_name].parent
        while current is not None:
            chain.append(current)
            current = self.entities[current].parent
        return chain

    def common_ancestor(self, entity_a: str, entity_b: str) -> str | None:
        """두 엔티티의 최근접 공통 조상 엔티티 이름. 계약에 없거나 관계가 없으면 None."""
        if entity_a not in self.entities or entity_b not in self.entities:
            return None
        chain_b = set(self.ancestors(entity_b))
        for name in self.ancestors(entity_a):
            if name in chain_b:
                return name
        return None
